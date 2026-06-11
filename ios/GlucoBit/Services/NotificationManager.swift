import Foundation
import UserNotifications

/// Local low/high glucose alerts, mirroring the firmware's thresholds
/// (low < 70 mg/dL / 3.9 mmol; high > 180; very high > 250) and its
/// one-alert-per-excursion behavior (`last_triggered_value`).
final class NotificationManager: NSObject, UNUserNotificationCenterDelegate {
    private var lastAlertedStatus: GlucoseStatus?

    func requestAuthorization() async -> Bool {
        let center = UNUserNotificationCenter.current()
        return (try? await center.requestAuthorization(options: [.alert, .sound, .badge])) ?? false
    }

    /// Called after each new reading. Fires once per excursion: re-arms only
    /// when glucose returns to range.
    func evaluate(reading: GlucoseReading, useMmol: Bool) {
        let status = GlucoseStatus(mgdl: reading.valueMgdl)

        guard status != .inRange else {
            lastAlertedStatus = nil
            return
        }
        guard status != lastAlertedStatus, !reading.isStale else { return }
        lastAlertedStatus = status

        let content = UNMutableNotificationContent()
        content.interruptionLevel = .timeSensitive
        content.sound = .defaultCritical
        let value = reading.displayValue(mmol: useMmol)
        let unit = useMmol ? "mmol/L" : "mg/dL"

        switch status {
        case .low:
            content.title = "Low Glucose"
            content.body = "\(value) \(unit) — below your low threshold."
        case .high:
            content.title = "High Glucose"
            content.body = "\(value) \(unit) — above your high threshold."
        case .veryHigh:
            content.title = "Very High Glucose"
            content.body = "\(value) \(unit) — well above your high threshold."
        case .inRange, .noData:
            return
        }

        let request = UNNotificationRequest(
            identifier: "glucose-alert-\(reading.date.timeIntervalSince1970)",
            content: content,
            trigger: nil
        )
        UNUserNotificationCenter.current().add(request)
    }

    // Show alerts even when the app is foregrounded.
    func userNotificationCenter(
        _ center: UNUserNotificationCenter,
        willPresent notification: UNNotification
    ) async -> UNNotificationPresentationOptions {
        [.banner, .sound]
    }
}
