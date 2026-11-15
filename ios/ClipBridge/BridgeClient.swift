import CryptoKit
import Foundation

struct Pairing: Codable {
    let host: String
    let port: Int
    let key: Data

    init(link: String) throws {
        guard let url = URLComponents(string: link.trimmingCharacters(in: .whitespacesAndNewlines)),
              url.scheme?.lowercased() == "clipbridge", url.path == "/pair",
              url.user == nil, url.password == nil, url.fragment == nil,
              let host = url.host, Self.isLocalIPv4(host),
              let port = url.port, (1...65535).contains(port),
              let query = url.queryItems, query.count == 1, query[0].name == "key",
              let encodedKey = query[0].value, encodedKey.utf8.count == 43,
              let key = Data(base64Encoded: encodedKey.replacingOccurrences(of: "-", with: "+")
                .replacingOccurrences(of: "_", with: "/") + "="), key.count == 32 else {
            throw BridgeError.message("Use the pairing QR code from a ClipBridge PC on your local network.")
        }
        self.host = host
        self.port = port
        self.key = key
    }

    private static func isLocalIPv4(_ host: String) -> Bool {
        let parts = host.split(separator: ".", omittingEmptySubsequences: false)
        let numbers = parts.compactMap { part -> UInt8? in
            guard let number = UInt8(part), String(number) == part else { return nil }
            return number
        }
        guard parts.count == 4, numbers.count == 4 else { return false }
        let first = numbers[0], second = numbers[1]
        return first == 10 || (first == 172 && (16...31).contains(second))
            || (first == 192 && second == 168) || (first == 169 && second == 254)
    }
}

enum BridgeError: LocalizedError {
    case message(String)

    var errorDescription: String? {
        switch self {
        case .message(let text): return text
        }
    }
}

final class BridgeClient: NSObject, URLSessionTaskDelegate {
    private enum Endpoint: String {
        case pair = "/v1/pair"
        case send = "/v1/clipboard"
        case current = "/v1/clipboard/current"
    }

    private struct Item: Codable {
        let kind: String
        let text: String
    }

    private struct Request: Encodable {
        let time = Date().timeIntervalSince1970
        let device: String
        let item: Item?
    }

    private struct Reply: Decodable {
        let ok: Bool
        let error: String?
        let paused: Bool?
        let item: Item?
    }

    private struct Envelope: Codable {
        let nonce: Data
        let data: Data
    }

    private let device: String
    private let session: URLSession

    init(device: String) {
        self.device = device
        let config = URLSessionConfiguration.ephemeral
        config.timeoutIntervalForRequest = 10
        config.timeoutIntervalForResource = 15
        config.waitsForConnectivity = true
        config.requestCachePolicy = .reloadIgnoringLocalCacheData
        config.httpShouldSetCookies = false
        session = URLSession(configuration: config)
    }

    func pair(with pairing: Pairing) async throws -> Bool {
        try await request(.pair, to: pairing).paused ?? false
    }

    func send(_ text: String, to pairing: Pairing) async throws {
        guard !text.isEmpty, text.utf8.count <= 1024 * 1024, !text.utf8.contains(0) else {
            throw BridgeError.message("Enter text up to 1 MB without null characters.")
        }
        _ = try await request(.send, to: pairing, item: Item(kind: "text", text: text))
    }

    func currentText(from pairing: Pairing) async throws -> String? {
        guard let item = try await request(.current, to: pairing).item else { return nil }
        guard item.kind == "text" else { throw BridgeError.message("The PC returned an unsupported item.") }
        return item.text
    }

    private func request(_ endpoint: Endpoint, to pairing: Pairing, item: Item? = nil) async throws -> Reply {
        let path = endpoint.rawValue
        var address = URLComponents()
        address.scheme = "http"
        address.host = pairing.host
        address.port = pairing.port
        address.path = path
        guard let url = address.url else { throw BridgeError.message("Invalid PC address. Scan the QR code again.") }

        let key = SymmetricKey(data: pairing.key)
        let encoder = JSONEncoder()
        let plaintext = try encoder.encode(Request(device: device, item: item))
        let sealed = try AES.GCM.seal(plaintext, using: key, authenticating: Data("CB1 \(path)".utf8))
        let nonce = Data(sealed.nonce)
        let envelope = Envelope(nonce: nonce, data: sealed.ciphertext + sealed.tag)
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.httpBody = try encoder.encode(envelope)

        let (bytes, response) = try await session.bytes(for: request, delegate: self)
        if (response as? HTTPURLResponse)?.statusCode == 401 {
            throw BridgeError.message("The PC rejected the pairing. Check automatic date and time on both devices or scan a new QR code.")
        }
        guard (response as? HTTPURLResponse)?.statusCode == 200 else {
            throw BridgeError.message("Unexpected response. Check that ClipBridge is running on your PC.")
        }
        // JSON can escape a single ASCII byte as six bytes before Base64 encoding.
        let limit = 8 * 1024 * 1024 + 4096
        let expectedLength = response.expectedContentLength
        guard expectedLength <= limit else { throw BridgeError.message("The PC response is too large.") }
        var body = Data()
        body.reserveCapacity(Int(max(0, expectedLength)))
        for try await byte in bytes {
            guard body.count < limit else { throw BridgeError.message("The PC response is too large.") }
            body.append(byte)
        }

        let decoder = JSONDecoder()
        let reply: Reply
        do {
            let wire = try decoder.decode(Envelope.self, from: body)
            let replyNonce = try AES.GCM.Nonce(data: wire.nonce)
            let box = try AES.GCM.SealedBox(nonce: replyNonce, ciphertext: wire.data.dropLast(16), tag: wire.data.suffix(16))
            let aad = Data("CB1 reply \(path) \(nonce.base64EncodedString())".utf8)
            let plaintext = try AES.GCM.open(box, using: key, authenticating: aad)
            reply = try decoder.decode(Reply.self, from: plaintext)
        } catch {
            throw BridgeError.message("The PC response could not be verified. Scan the current pairing QR code and try again.")
        }
        guard reply.ok else {
            if reply.error == "Unknown endpoint" {
                throw BridgeError.message("Open the Windows build included with this iPhone prototype, then scan its QR code.")
            }
            throw BridgeError.message(reply.error ?? "The PC could not complete the request.")
        }
        return reply
    }

    func urlSession(_ session: URLSession, task: URLSessionTask, willPerformHTTPRedirection response: HTTPURLResponse,
                    newRequest request: URLRequest, completionHandler: @escaping (URLRequest?) -> Void) {
        completionHandler(nil)
    }
}
