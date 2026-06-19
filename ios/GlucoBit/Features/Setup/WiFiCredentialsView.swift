import SwiftUI

struct WiFiCredentialsView: View {
    @Binding var ssid: String
    @Binding var password: String
    let device: any DeviceManaging
    let onNext: () -> Void

    var body: some View {
        Form {
            WiFiCredentialsFields(ssid: $ssid, password: $password, device: device)
        }
        .navigationTitle("WiFi Network")
        .scrollContentBackground(.hidden)
        .background(AppTheme.background)
        .tint(AppTheme.accent)
        .toolbar {
            ToolbarItem(placement: .confirmationAction) {
                Button("Next", action: onNext)
                    .disabled(ssid.isEmpty)
            }
        }
    }
}

struct WiFiCredentialsFields: View {
    @Binding var ssid: String
    @Binding var password: String
    let device: (any DeviceManaging)?

    @State private var networks: [WiFiNetwork] = []
    @State private var isScanning = false
    @State private var scanError: String?

    var body: some View {
        Section {
            if let device {
                Button {
                    Task { await scan(device) }
                } label: {
                    Label(isScanning ? "Scanning..." : "Scan nearby networks", systemImage: "wifi")
                }
                .disabled(isScanning)

                ForEach(networks) { network in
                    Button {
                        ssid = network.ssid
                    } label: {
                        HStack {
                            Text(network.ssid)
                            Spacer()
                            Text("\(network.rssi) dBm")
                                .foregroundStyle(.secondary)
                            if ssid == network.ssid {
                                Image(systemName: "checkmark")
                            }
                        }
                    }
                    .buttonStyle(.plain)
                }
            }

            TextField("Network name (SSID)", text: $ssid)
                .textInputAutocapitalization(.never)
                .autocorrectionDisabled()
            SecureField("Password", text: $password)
        } footer: {
            Text("Enter Your WiFi Credentials")
        }

        if let scanError {
            Section {
                Label(scanError, systemImage: "exclamationmark.triangle")
                    .foregroundStyle(.orange)
            }
        }
    }

    @MainActor private func scan(_ device: any DeviceManaging) async {
        isScanning = true
        scanError = nil
        do {
            networks = try await device.scanWiFiNetworks()
            if networks.isEmpty {
                scanError = "No visible 2.4 GHz networks found. Enter the network name manually."
            }
        } catch {
            scanError = error.localizedDescription
        }
        isScanning = false
    }
}
