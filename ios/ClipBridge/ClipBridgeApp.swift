import SwiftUI
import UIKit

@main
@MainActor
struct ClipBridgeApp: App {
    var body: some Scene {
        WindowGroup { ContentView() }
    }
}

@MainActor
final class BridgeModel: ObservableObject {
    @Published private(set) var pairing: Pairing?
    @Published private(set) var receivedText: String?
    @Published private(set) var status: String?
    @Published private(set) var error: String?
    @Published private(set) var busy = false

    private let client: BridgeClient

    init() {
        let defaults = UserDefaults.standard
        let device = defaults.string(forKey: "deviceID") ?? "ios-\(UUID().uuidString)"
        defaults.set(device, forKey: "deviceID")
        client = BridgeClient(device: device)
        do {
            pairing = try PairingStore.load()
        } catch {
            report(error.localizedDescription)
        }
    }

    func pair(_ candidate: Pairing) async {
        await run("Verifying pairing…") {
            let paused = try await client.pair(with: candidate)
            try PairingStore.save(candidate)
            pairing = candidate
            receivedText = nil
            return paused ? "Paired. Start syncing on the PC to transfer text." : "Paired with your PC."
        }
    }

    func send(_ text: String) async {
        guard let pairing else { return }
        await run("Sending…") {
            try await client.send(text, to: pairing)
            return "Sent to the Windows clipboard."
        }
    }

    func getFromPC() async {
        guard let pairing, !busy else { return }
        receivedText = nil
        await run("Reading the PC clipboard…") {
            receivedText = try await client.currentText(from: pairing)
            return receivedText == nil ? "Copy some text on your PC, then try again." : "Text received."
        }
    }

    func copyReceivedText() {
        guard let receivedText else { return }
        UIPasteboard.general.setObjects([receivedText as NSString], localOnly: true, expirationDate: nil)
        error = nil
        status = "Copied to the iPhone clipboard."
    }

    func forgetPC() {
        do {
            try PairingStore.remove()
            pairing = nil
            receivedText = nil
            error = nil
            status = nil
        } catch {
            report(error.localizedDescription)
        }
    }

    func report(_ message: String) {
        error = message
        status = nil
    }

    private func run(_ progress: String, operation: () async throws -> String) async {
        guard !busy else { return }
        busy = true
        error = nil
        status = progress
        defer { busy = false }
        do {
            status = try await operation()
        } catch is URLError {
            report("Couldn’t reach the PC. Check ClipBridge, Wi‑Fi, Local Network access, and the Windows firewall. Scan the QR code again if the PC address changed.")
        } catch {
            report(error.localizedDescription)
        }
    }
}
