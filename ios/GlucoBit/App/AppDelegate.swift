import UIKit
import UserNotifications

/// Owns the object graph. Created via UIApplicationDelegateAdaptor so the
/// CBCentralManager (with its state-restoration identifier) exists as early
/// as possible when iOS relaunches the app for a BLE event.
@MainActor
final class AppContainer {
    let settings: AppSettings
    let store: GlucoseStore
    let notifications: NotificationManager
    let healthKit: HealthKitExporter
    let sync: GlucoseSyncService
    let device: any DeviceManaging
    let relay: GlucoseRelay

    init() {
        settings = AppSettings()
        store = GlucoseStore()
        notifications = NotificationManager()
        healthKit = HealthKitExporter()
        sync = GlucoseSyncService(
            store: store,
            settings: settings,
            notifications: notifications,
            healthKit: healthKit
        )
        #if targetEnvironment(simulator)
        device = MockDeviceManager()
        #else
        device = DeviceManager(settings: settings)
        #endif
        relay = GlucoseRelay(device: device, sync: sync)
    }
}

final class AppDelegate: NSObject, UIApplicationDelegate {
    @MainActor lazy var container = AppContainer()

    func application(
        _ application: UIApplication,
        didFinishLaunchingWithOptions launchOptions: [UIApplication.LaunchOptionsKey: Any]? = nil
    ) -> Bool {
        // Touching `container` here instantiates the CBCentralManager, which
        // is required for CoreBluetooth state restoration to complete.
        MainActor.assumeIsolated {
            UNUserNotificationCenter.current().delegate = container.notifications
            BackgroundRefreshScheduler.register(
                sync: container.sync,
                relay: container.relay,
                device: container.device
            )
        }
        return true
    }
}
