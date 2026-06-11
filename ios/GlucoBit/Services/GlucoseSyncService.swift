import Foundation
import Observation
import WidgetKit

/// Coordinates Dexcom fetches with the local store, notifications, HealthKit
/// and widget refresh. Single entry point used by the foreground timer, the
/// BLE relay and the background refresh task.
@Observable
@MainActor
final class GlucoseSyncService {
    enum SyncState: Equatable {
        case idle
        case syncing
        case failed(String)
    }

    let store: GlucoseStore
    let client: DexcomShareClient
    private let settings: AppSettings
    private let notifications: NotificationManager
    private let healthKit: HealthKitExporter

    private(set) var state: SyncState = .idle
    private(set) var lastSyncDate: Date?
    private var foregroundTimer: Timer?

    init(
        store: GlucoseStore,
        settings: AppSettings,
        notifications: NotificationManager,
        healthKit: HealthKitExporter
    ) {
        self.store = store
        self.settings = settings
        self.notifications = notifications
        self.healthKit = healthKit
        self.client = DexcomShareClient()
        Task { await reloadCredentials() }
    }

    func reloadCredentials() async {
        if let creds = KeychainStore.dexcomCredentials {
            await client.configure(creds)
        }
    }

    /// Fetch latest readings and fan out to store, alerts, HealthKit, widget.
    /// Returns the latest reading (also when the fetch was throttled and the
    /// cached value is still current).
    @discardableResult
    func sync(force: Bool = false) async -> GlucoseReading? {
        state = .syncing
        do {
            let readings = try await client.fetchReadings(force: force)
            store.ingest(readings)
            state = .idle
            lastSyncDate = Date()

            if let latest = store.latest {
                if settings.notificationsEnabled {
                    notifications.evaluate(reading: latest, useMmol: settings.useMmol)
                }
                if settings.healthKitEnabled {
                    await healthKit.export(readings)
                }
            }
            WidgetCenter.shared.reloadAllTimelines()
            return store.latest
        } catch DexcomShareClient.ClientError.throttled {
            state = .idle
            return store.latest
        } catch {
            state = .failed(error.localizedDescription)
            return store.latest
        }
    }

    /// 90-second foreground polling, matching the device's cadence.
    func startForegroundPolling() {
        stopForegroundPolling()
        Task { await sync() }
        foregroundTimer = Timer.scheduledTimer(withTimeInterval: 90, repeats: true) { [weak self] _ in
            Task { @MainActor in await self?.sync() }
        }
    }

    func stopForegroundPolling() {
        foregroundTimer?.invalidate()
        foregroundTimer = nil
    }
}
