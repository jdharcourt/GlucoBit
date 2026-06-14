import Foundation
import Observation
import WidgetKit

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
                    notifications.evaluate(
                        reading: latest,
                        useMmol: settings.useMmol,
                        lowMgdl: settings.alertLowMgdl,
                        highMgdl: settings.alertHighMgdl
                    )
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
