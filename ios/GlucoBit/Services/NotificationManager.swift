import Foundation
import UserNotifications

final class NotificationManager: NSObject, UNUserNotificationCenterDelegate {
    private var lastAlertedStatus: GlucoseStatus?

    func requestAuthorization() async -> Bool {
        let center = UNUserNotificationCenter.current()
        return (try? await center.requestAuthorization(options: [.alert, .sound, .badge])) ?? false
    }

    func evaluate(reading: GlucoseReading, useMmol: Bool, lowMgdl: Int, highMgdl: Int) {
        let status = GlucoseStatus(mgdl: reading.valueMgdl, lowMgdl: lowMgdl, highMgdl: highMgdl)

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
            content.body = "\(value) \(unit) is below your low threshold."
        case .high:
            content.title = "High Glucose"
            content.body = "\(value) \(unit) is above your high threshold."
        case .veryHigh:
            content.title = "Very High Glucose"
            content.body = "\(value) \(unit) is well above your high threshold."
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

    func userNotificationCenter(
        _ center: UNUserNotificationCenter,
        willPresent notification: UNNotification
    ) async -> UNNotificationPresentationOptions {
        [.banner, .sound]
    }
}
