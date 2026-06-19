import Foundation
import Observation

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
    var alertLowMgdl: Int {
        didSet { Self.defaults.set(alertLowMgdl, forKey: "ALERT_LOW_MGDL") }
    }
    var alertHighMgdl: Int {
        didSet { Self.defaults.set(alertHighMgdl, forKey: "ALERT_HIGH_MGDL") }
    }
    var noDataAlarmEnabled: Bool {
        didSet { Self.defaults.set(noDataAlarmEnabled, forKey: "NO_DATA_ALARM_ENABLED") }
    }
    var noDataAlarmMinutes: Int {
        didSet { Self.defaults.set(noDataAlarmMinutes, forKey: "NO_DATA_ALARM_MINUTES") }
    }
    var timezoneAutomatic: Bool {
        didSet { Self.defaults.set(timezoneAutomatic, forKey: "TIMEZONE_AUTOMATIC") }
    }
    var timezoneOffsetMinutes: Int {
        didSet { Self.defaults.set(timezoneOffsetMinutes, forKey: "TIMEZONE_OFFSET_MINUTES") }
    }
    var notificationsEnabled: Bool {
        didSet { Self.defaults.set(notificationsEnabled, forKey: "NOTIFICATIONS_ENABLED") }
    }
    var healthKitEnabled: Bool {
        didSet { Self.defaults.set(healthKitEnabled, forKey: "HEALTHKIT_ENABLED") }
    }
    var deviceConfigured: Bool {
        didSet { Self.defaults.set(deviceConfigured, forKey: "DEVICE_CONFIGURED") }
    }
    var pairedDeviceID: String? {
        didSet { Self.defaults.set(pairedDeviceID, forKey: "PAIRED_DEVICE_ID") }
    }

    init() {
        let d = Self.defaults
        useMmol = d.object(forKey: "MMOL") as? Bool ?? true
        displayName = d.string(forKey: "DISPLAY_NAME") ?? ""
        backgroundColorHex = d.string(forKey: "BACKGROUND_COLOR") ?? DeviceTheme.defaultBackgroundHex
        deviceUITheme = d.object(forKey: "UI_THEME") as? Int ?? 1
        alertLowMgdl = d.object(forKey: "ALERT_LOW_MGDL") as? Int ?? 70
        alertHighMgdl = d.object(forKey: "ALERT_HIGH_MGDL") as? Int ?? 180
        noDataAlarmEnabled = d.object(forKey: "NO_DATA_ALARM_ENABLED") as? Bool ?? true
        noDataAlarmMinutes = d.object(forKey: "NO_DATA_ALARM_MINUTES") as? Int ?? 15
        timezoneAutomatic = d.object(forKey: "TIMEZONE_AUTOMATIC") as? Bool ?? true
        timezoneOffsetMinutes = d.object(forKey: "TIMEZONE_OFFSET_MINUTES") as? Int ?? Self.currentTimezoneOffsetMinutes
        notificationsEnabled = d.object(forKey: "NOTIFICATIONS_ENABLED") as? Bool ?? false
        healthKitEnabled = d.object(forKey: "HEALTHKIT_ENABLED") as? Bool ?? false
        deviceConfigured = d.bool(forKey: "DEVICE_CONFIGURED")
        pairedDeviceID = d.string(forKey: "PAIRED_DEVICE_ID")
    }

    static func widgetSnapshot() -> (
        useMmol: Bool,
        backgroundColorHex: String,
        alertLowMgdl: Int,
        alertHighMgdl: Int
    ) {
        let d = defaults
        return (
            d.object(forKey: "MMOL") as? Bool ?? true,
            d.string(forKey: "BACKGROUND_COLOR") ?? DeviceTheme.defaultBackgroundHex,
            d.object(forKey: "ALERT_LOW_MGDL") as? Int ?? 70,
            d.object(forKey: "ALERT_HIGH_MGDL") as? Int ?? 180
        )
    }

    static var currentTimezoneOffsetMinutes: Int {
        TimeZone.current.secondsFromGMT() / 60
    }
}
