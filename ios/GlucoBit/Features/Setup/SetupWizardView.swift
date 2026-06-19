import SwiftUI

struct SetupWizardView: View {
    @Environment(\.dismiss) private var dismiss
    let device: any DeviceManaging
    let settings: AppSettings
    let sync: GlucoseSyncService

    @State private var path: [Step] = []
    @State private var wifiSSID = ""
    @State private var wifiPassword = ""
    @State private var dexcomUsername = ""
    @State private var dexcomPassword = ""
    @State private var dexcomServer = "shareous1.dexcom.com"
    @State private var displayName = ""

    enum Step: Hashable {
        case wifi
        case dexcom
        case progress
    }

    var body: some View {
        NavigationStack(path: $path) {
            DeviceScanView(device: device) {
                path.append(.wifi)
            }
            .navigationTitle("Find Your GlucoBit")
            .navigationDestination(for: Step.self) { step in
                switch step {
                case .wifi:
                    WiFiCredentialsView(ssid: $wifiSSID, password: $wifiPassword, device: device) {
                        path.append(.dexcom)
                    }
                case .dexcom:
                    DexcomCredentialsView(
                        username: $dexcomUsername,
                        password: $dexcomPassword,
                        server: $dexcomServer,
                        displayName: $displayName,
                        sync: sync
                    ) {
                        path.append(.progress)
                    }
                case .progress:
                    SetupProgressView(
                        device: device,
                        payload: provisioningPayload
                    ) {
                        completeSetup()
                    }
                }
            }
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("Cancel") { dismiss() }
                }
            }
        }
        .interactiveDismissDisabled()
    }

    private var provisioningPayload: [SettingsProvisioner.SettingsKey: Any] {
        [
            .wifiSSID: wifiSSID,
            .wifiPassword: wifiPassword,
            .dexcomUsername: dexcomUsername,
            .dexcomPassword: dexcomPassword,
            .dexcomServer: dexcomServer,
            .displayName: displayName.isEmpty ? "GlucoBit" : displayName,
            .mmol: settings.useMmol,
            .alertLowMgdl: settings.alertLowMgdl,
            .alertHighMgdl: settings.alertHighMgdl,
            .noDataAlarmEnabled: settings.noDataAlarmEnabled,
            .noDataAlarmMinutes: settings.noDataAlarmMinutes,
            .setupMode: false,
        ]
    }

    private func completeSetup() {
        KeychainStore.set(dexcomUsername, for: .dexcomUsername)
        KeychainStore.set(dexcomPassword, for: .dexcomPassword)
        KeychainStore.set(dexcomServer, for: .dexcomServer)
        KeychainStore.set(wifiSSID, for: .deviceWifiSSID)
        KeychainStore.set(wifiPassword, for: .deviceWifiPassword)
        settings.displayName = displayName.isEmpty ? "GlucoBit" : displayName
        settings.deviceConfigured = true
        Task {
            await sync.reloadCredentials()
            await sync.sync(force: true)
        }
        dismiss()
    }
}
