import SwiftUI

struct DeviceScanView: View {
    let device: any DeviceManaging
    let onConnected: () -> Void

    var body: some View {
        List {
            Section {
                if device.connectionState == .bluetoothOff {
                    Label("Turn on Bluetooth to find your GlucoBit",
                          systemImage: "exclamationmark.triangle")
                        .foregroundStyle(.orange)
                } else if device.discoveredDevices.isEmpty {
                    HStack {
                        ProgressView()
                        Text("Scanning for devices…")
                            .foregroundStyle(.secondary)
                            .padding(.leading, 8)
                    }
                }

                ForEach(device.discoveredDevices) { found in
                    Button {
                        device.connect(to: found.id)
                    } label: {
                        HStack {
                            VStack(alignment: .leading) {
                                Text(found.name)
                                    .font(.headline)
                                Text(signalDescription(rssi: found.rssi))
                                    .font(.caption)
                                    .foregroundStyle(.secondary)
                            }
                            Spacer()
                            if device.connectionState == .connecting {
                                ProgressView()
                            } else {
                                Image(systemName: "wave.3.right")
                                    .foregroundStyle(signalColor(rssi: found.rssi))
                            }
                        }
                    }
                }
            } footer: {
                Text("Make sure your GlucoBit is plugged in and nearby.")
            }
        }
        .scrollContentBackground(.hidden)
        .background(AppTheme.background)
        .tint(AppTheme.accent)
        .onAppear { device.startScanning() }
        .onDisappear { device.stopScanning() }
        .onChange(of: device.connectionState) { _, state in
            if state == .connected { onConnected() }
        }
    }

    private func signalDescription(rssi: Int) -> String {
        switch rssi {
        case (-60)...: return "Excellent signal"
        case (-75)...: return "Good signal"
        default: return "Weak signal — move closer"
        }
    }

    private func signalColor(rssi: Int) -> Color {
        switch rssi {
        case (-60)...: return .green
        case (-75)...: return .yellow
        default: return .orange
        }
    }
}
