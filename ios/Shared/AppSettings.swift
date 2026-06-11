import Foundation
import Observation

/// App-side preferences, persisted in the App Group so the widget can render
/// with the same unit and colors. Mirrors the device's display settings where
/// they overlap (MMOL, BACKGROUND_COLOR, DISPLAY_NAME, UI_THEME).
@Observable
final class AppSettings {
    private static var defaults: UserDefaults {
        UserDefaults(suiteName: AppGroup.identifier) ?? .standard
    }

    var useMmol: Bool {
        didSet { Self.defaults.set(useMmol, forKey: "MMOL") }
    }
    var displayName: String {
        didSet { Self.defaults.set(displayName, forKey: "DISPLAY_NAME") }
    }
    var backgroundColorHex: String {
        didSet { Self.defaults.set(backgroundColorHex, forKey: "BACKGROUND_COLOR") }
    }
    var deviceUITheme: Int {
        didSet { Self.defaults.set(deviceUITheme, forKey: "UI_THEME") }
    }
    var notificationsEnabled: Bool {
        didSet { Self.defaults.set(notificationsEnabled, forKey: "NOTIFICATIONS_ENABLED") }
    }
    var healthKitEnabled: Bool {
        didSet { Self.defaults.set(healthKitEnabled, forKey: "HEALTHKIT_ENABLED") }
    }
    /// Set once the setup wizard has provisioned a device.
    var deviceConfigured: Bool {
        didSet { Self.defaults.set(deviceConfigured, forKey: "DEVICE_CONFIGURED") }
    }
    /// CoreBluetooth peripheral identifier of the paired GlucoBit, for reconnects.
    var pairedDeviceID: String? {
        didSet { Self.defaults.set(pairedDeviceID, forKey: "PAIRED_DEVICE_ID") }
    }

    init() {
        let d = Self.defaults
        useMmol = d.object(forKey: "MMOL") as? Bool ?? true
        displayName = d.string(forKey: "DISPLAY_NAME") ?? ""
        backgroundColorHex = d.string(forKey: "BACKGROUND_COLOR") ?? DeviceTheme.defaultBackgroundHex
        deviceUITheme = d.object(forKey: "UI_THEME") as? Int ?? 1
        notificationsEnabled = d.object(forKey: "NOTIFICATIONS_ENABLED") as? Bool ?? false
        healthKitEnabled = d.object(forKey: "HEALTHKIT_ENABLED") as? Bool ?? false
        deviceConfigured = d.bool(forKey: "DEVICE_CONFIGURED")
        pairedDeviceID = d.string(forKey: "PAIRED_DEVICE_ID")
    }

    /// Read-only snapshot for the widget process (no Observation needed there).
    static func widgetSnapshot() -> (useMmol: Bool, backgroundColorHex: String) {
        let d = defaults
        return (
            d.object(forKey: "MMOL") as? Bool ?? true,
            d.string(forKey: "BACKGROUND_COLOR") ?? DeviceTheme.defaultBackgroundHex
        )
    }
}
