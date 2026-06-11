import Foundation
import Observation
import UIKit

/// Pushes Dexcom readings to the device over BLE when the device reports
/// `needs_data` (WiFi down or reading stale). Triggered by Device Status
/// notifications, which also wake the app from suspension thanks to the
/// bluetooth-central background mode.
@Observable
@MainActor
final class GlucoseRelay {
    enum RelayState: Equatable {
        case idle
        case relaying
        case lastPush(Date)
        case failed(String)
    }

    private(set) var state: RelayState = .idle

    private let device: any DeviceManaging
    private let sync: GlucoseSyncService
    private var relayTask: Task<Void, Never>?

    init(device: any DeviceManaging, sync: GlucoseSyncService) {
        self.device = device
        self.sync = sync
        device.onNeedsData = { [weak self] in
            self?.relayNow()
        }
    }

    /// Fetch the latest reading and push it to the device. Must finish within
    /// the short background window iOS grants for a BLE event, so the whole
    /// operation runs inside a UIKit background task.
    func relayNow() {
        guard relayTask == nil else { return }

        let bgTask = UIApplication.shared.beginBackgroundTask(withName: "glucose-relay")
        state = .relaying

        relayTask = Task {
            defer {
                relayTask = nil
                UIApplication.shared.endBackgroundTask(bgTask)
            }

            guard let latest = await sync.sync() else {
                state = .failed("No glucose data available to relay")
                return
            }
            // Don't push stale data to the device — better to let it show
            // its own "no data" state than a misleading old value.
            guard !latest.isStale else {
                state = .failed("Latest Dexcom reading is stale")
                return
            }

            do {
                let payload = GlucoBitGATT.encodeGlucosePush(
                    latest: latest,
                    previous: sync.store.previous
                )
                try await device.writeGlucose(payload)
                try await SettingsProvisioner(device: device)
                    .awaitAck(op: .glucoseAck, timeout: 10)
                state = .lastPush(Date())
            } catch {
                state = .failed(error.localizedDescription)
            }
        }
    }
}
