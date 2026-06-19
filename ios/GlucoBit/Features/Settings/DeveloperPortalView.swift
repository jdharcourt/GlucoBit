import SwiftUI

struct DeveloperPortalView: View {
    let device: any DeviceManaging
    let sync: GlucoseSyncService

    @State private var token = ""
    @State private var unlocked = false
    @State private var runningCommand: String?
    @State private var results: [DeveloperResult] = []
    @State private var error: String?

    private var storedToken: String? {
        KeychainStore.get(.developerPortalToken)
    }

    var body: some View {
        Group {
            if unlocked {
                portal
            } else {
                gate
            }
        }
        .navigationTitle("Developer Portal")
        .scrollContentBackground(.hidden)
        .background(AppTheme.background)
        .tint(AppTheme.accent)
    }

    private var gate: some View {
        Form {
            Section(storedToken == nil ? "Create Token" : "Access Token") {
                SecureField(storedToken == nil ? "New token" : "Token", text: $token)
                    .textInputAutocapitalization(.never)
                    .autocorrectionDisabled()
                Button(storedToken == nil ? "Set Token" : "Unlock") {
                    unlock()
                }
                .disabled(token.count < 8)
            }
            if let error {
                Section {
                    Label(error, systemImage: "xmark.octagon")
                        .foregroundStyle(.red)
                }
            }
        }
    }

    private var portal: some View {
        Form {
            Section("Connection") {
                LabeledContent("Bluetooth", value: String(describing: device.connectionState))
                if let status = device.deviceStatus {
                    LabeledContent("Firmware", value: status.firmwareVersion)
                    LabeledContent("WiFi", value: status.wifiConnected ? "Connected" : "Disconnected")
                    if let age = status.readingAgeSeconds {
                        LabeledContent("Reading age", value: "\(age)s")
                    }
                }
                Button(device.connectionState == .scanning ? "Stop scan" : "Scan for GlucoBit") {
                    if device.connectionState == .scanning {
                        device.stopScanning()
                    } else {
                        device.startScanning()
                    }
                }
                if device.connectionState == .connected {
                    Button("Disconnect") { device.disconnect() }
                }
                ForEach(device.discoveredDevices) { discovered in
                    Button("\(discovered.name) \(discovered.rssi)dBm") {
                        device.connect(to: discovered.id)
                    }
                }
            }

            Section("Tests") {
                Button("Data connectivity") { runDataTest() }
                Button("WiFi") { runDeviceCommand("wifi") }
                Button("Bluetooth") { runDeviceCommand("bluetooth") }
                Button("LED") { runDeviceCommand("led") }
                Button("Screen") { runDeviceCommand("screen") }
                Button("Alarm") { runDeviceCommand("alarm") }
                Button("Full status") { runDeviceCommand("status") }
                Button("WiFi scan") { runDeviceCommand("wifi_scan") }
            }
            .disabled(runningCommand != nil)

            if let runningCommand {
                Section {
                    Label("Running \(runningCommand)…", systemImage: "clock")
                }
            }

            Section("Results") {
                if results.isEmpty {
                    Text("No tests run")
                        .foregroundStyle(.secondary)
                }
                ForEach(results) { result in
                    VStack(alignment: .leading, spacing: 4) {
                        Text(result.name)
                            .font(.headline)
                        Text(result.message)
                            .font(.system(.footnote, design: .monospaced))
                            .textSelection(.enabled)
                        Text(result.date, format: .dateTime.hour().minute().second())
                            .font(.caption)
                            .foregroundStyle(.secondary)
                    }
                }
            }

            Section {
                Button("Lock") {
                    token = ""
                    unlocked = false
                }
                Button("Reset token", role: .destructive) {
                    KeychainStore.delete(.developerPortalToken)
                    token = ""
                    unlocked = false
                }
            }
        }
    }

    private func unlock() {
        if let storedToken {
            guard token == storedToken else {
                error = "Invalid token."
                return
            }
            error = nil
            unlocked = true
        } else {
            KeychainStore.set(token, for: .developerPortalToken)
            error = nil
            unlocked = true
        }
    }

    private func runDataTest() {
        runningCommand = "Data connectivity"
        Task { @MainActor in
            let reading = await sync.sync(force: true)
            appendResult("Data connectivity", reading.map { "Latest: \($0.valueMgdl) mg/dL at \($0.date)" } ?? "No reading returned")
            runningCommand = nil
        }
    }

    private func runDeviceCommand(_ command: String) {
        runningCommand = command
        Task { @MainActor in
            do {
                appendResult(command, try await device.runDeveloperCommand(command))
            } catch {
                appendResult(command, error.localizedDescription)
            }
            runningCommand = nil
        }
    }

    private func appendResult(_ name: String, _ message: String) {
        results.insert(DeveloperResult(name: name, message: message), at: 0)
        if results.count > 20 {
            results.removeLast()
        }
    }
}

private struct DeveloperResult: Identifiable {
    let id = UUID()
    let name: String
    let message: String
    let date = Date()
}
