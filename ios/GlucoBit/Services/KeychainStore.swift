import Foundation
import Security

/// Minimal Keychain wrapper for credentials (Dexcom account, device WiFi).
enum KeychainStore {
    private static let service = "com.jdharcourt.glucobit"

    enum Key: String {
        case dexcomUsername = "dexcom-username"
        case dexcomPassword = "dexcom-password"
        case dexcomServer = "dexcom-server"
        case deviceWifiSSID = "device-wifi-ssid"
        case deviceWifiPassword = "device-wifi-password"
        case developerPortalToken = "developer-portal-token"
    }

    static func set(_ value: String, for key: Key) {
        let data = Data(value.utf8)
        let query: [String: Any] = [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrService as String: service,
            kSecAttrAccount as String: key.rawValue,
        ]
        let attributes: [String: Any] = [kSecValueData as String: data]
        let status = SecItemUpdate(query as CFDictionary, attributes as CFDictionary)
        if status == errSecItemNotFound {
            var addQuery = query
            addQuery[kSecValueData as String] = data
            addQuery[kSecAttrAccessible as String] = kSecAttrAccessibleAfterFirstUnlock
            SecItemAdd(addQuery as CFDictionary, nil)
        }
    }

    static func get(_ key: Key) -> String? {
        let query: [String: Any] = [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrService as String: service,
            kSecAttrAccount as String: key.rawValue,
            kSecReturnData as String: true,
            kSecMatchLimit as String: kSecMatchLimitOne,
        ]
        var result: AnyObject?
        guard SecItemCopyMatching(query as CFDictionary, &result) == errSecSuccess,
              let data = result as? Data else { return nil }
        return String(decoding: data, as: UTF8.self)
    }

    static func delete(_ key: Key) {
        let query: [String: Any] = [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrService as String: service,
            kSecAttrAccount as String: key.rawValue,
        ]
        SecItemDelete(query as CFDictionary)
    }

    static var dexcomCredentials: DexcomShareClient.Credentials? {
        guard let username = get(.dexcomUsername), !username.isEmpty,
              let password = get(.dexcomPassword),
              let server = get(.dexcomServer) else { return nil }
        return .init(username: username, password: password, server: server)
    }
}
