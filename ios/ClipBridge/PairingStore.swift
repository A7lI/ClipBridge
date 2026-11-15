import Foundation
import Security

enum PairingStore {
    private static let query: [String: Any] = [
        kSecClass as String: kSecClassGenericPassword,
        kSecAttrService as String: "app.clipbridge.ios",
        kSecAttrAccount as String: "paired-pc"
    ]

    static func load() throws -> Pairing? {
        var lookup = query
        lookup[kSecReturnData as String] = true
        lookup[kSecMatchLimit as String] = kSecMatchLimitOne
        var result: CFTypeRef?
        let status = SecItemCopyMatching(lookup as CFDictionary, &result)
        if status == errSecItemNotFound { return nil }
        guard status == errSecSuccess, let data = result as? Data else {
            throw BridgeError.message("Could not read the saved pairing from Keychain.")
        }
        return try JSONDecoder().decode(Pairing.self, from: data)
    }

    static func save(_ pairing: Pairing) throws {
        let data = try JSONEncoder().encode(pairing)
        let update = [kSecValueData as String: data]
        var status = SecItemUpdate(query as CFDictionary, update as CFDictionary)
        if status == errSecItemNotFound {
            var item = query
            item[kSecValueData as String] = data
            item[kSecAttrAccessible as String] = kSecAttrAccessibleWhenUnlockedThisDeviceOnly
            status = SecItemAdd(item as CFDictionary, nil)
        }
        guard status == errSecSuccess else {
            throw BridgeError.message("Could not save the pairing in Keychain.")
        }
    }

    static func remove() throws {
        let status = SecItemDelete(query as CFDictionary)
        guard status == errSecSuccess || status == errSecItemNotFound else {
            throw BridgeError.message("Could not clear the saved pairing from Keychain.")
        }
    }
}
