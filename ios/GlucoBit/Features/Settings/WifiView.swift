import SwiftUI

struct WifiView: View {
    let device: any DeviceManaging

    @Environment(\.dismiss) private var dismiss
    @State private var wifiSSID = KeychainStore.get(.deviceWifiSSID) ?? ""
    @State private var wifiPassword = KeychainStore.get(.deviceWifiPassword) ?? ""
    @State private var sending = false
    @State private var error: String?

    var body: some View {
        Form {
            Section("WiFi Login") {
                WiFiCredentialsFields(ssid: $wifiSSID, password: $wifiPassword, device: connectedDevice)
            }

            if device.connectionState != .connected {
                Section {
                    Label("WiFi will save in the app. Connect over Bluetooth to push it to GlucoBit.",
                          systemImage: "antenna.radiowaves.left.and.right.slash")
                        .foregroundStyle(.orange)
                }
            }

            if let error {
                Section {
                    Label(error, systemImage: "xmark.octagon")
                        .foregroundStyle(.red)
                }
            }
        }
        .navigationTitle("WiFi Setup")
        .scrollContentBackground(.hidden)
        .background(AppTheme.background)
        .tint(AppTheme.accent)
        .toolbar {
            ToolbarItem(placement: .confirmationAction) {
                if sending {
                    ProgressView()
                } else {
                    Button("Apply") { apply() }
                        .disabled(wifiSSID.isEmpty)
                }
            }
        }
    }

    private var connectedDevice: (any DeviceManaging)? {
        device.connectionState == .connected ? device : nil
    }

    private func apply() {
        sending = true
        error = nil
        KeychainStore.set(wifiSSID, for: .deviceWifiSSID)
        KeychainStore.set(wifiPassword, for: .deviceWifiPassword)
        guard device.connectionState == .connected else {
            sending = false
            dismiss()
            return
        }
        Task {
            do {
                try await SettingsProvisioner(device: device).send([
                    .wifiSSID: wifiSSID,
                    .wifiPassword: wifiPassword,
                ])
                sending = false
                dismiss()
            } catch {
                sending = false
                self.error = error.localizedDescription
            }
        }
    }
}
