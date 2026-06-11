import Foundation
import BackgroundTasks

/// Opportunistic background refresh (BGAppRefreshTask). iOS decides when to
/// run these (typically a handful per day) — this is a backstop that keeps
/// the widget and HealthKit reasonably fresh, not a guaranteed cadence.
/// The primary background mechanism is the BLE needs_data notification.
@MainActor
enum BackgroundRefreshScheduler {
    static let taskIdentifier = "com.jdharcourt.glucobit.refresh"

    static func register(sync: GlucoseSyncService, relay: GlucoseRelay, device: any DeviceManaging) {
        BGTaskScheduler.shared.register(forTaskWithIdentifier: taskIdentifier, using: .main) { task in
            guard let refreshTask = task as? BGAppRefreshTask else { return }
            schedule()

            let work = Task { @MainActor in
                await sync.sync()
                if device.deviceStatus?.needsData == true {
                    relay.relayNow()
                }
                refreshTask.setTaskCompleted(success: true)
            }
            refreshTask.expirationHandler = {
                work.cancel()
                refreshTask.setTaskCompleted(success: false)
            }
        }
    }

    static func schedule() {
        let request = BGAppRefreshTaskRequest(identifier: taskIdentifier)
        request.earliestBeginDate = Date(timeIntervalSinceNow: 15 * 60)
        try? BGTaskScheduler.shared.submit(request)
    }
}
