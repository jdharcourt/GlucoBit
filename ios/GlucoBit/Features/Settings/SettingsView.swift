import SwiftUI

struct SettingsView: View {
    let settings: AppSettings
    let device: any DeviceManaging
    let sync: GlucoseSyncService
    let notifications: NotificationManager
    let healthKit: HealthKitExporter

    @State private var showSetupWizard = false

    var body: some View {
        Form {
            Section("Units") {
                Picker("Glucose unit", selection: Bindable(settings).useMmol) {
                    Text("mmol/L").tag(true)
                    Text("mg/dL").tag(false)
                }
            }

            Section("Alerts") {
                Toggle("Glucose notifications", isOn: Bindable(settings).notificationsEnabled)
                    .onChange(of: settings.notificationsEnabled) { _, enabled in
                        if enabled {
                            Task {
                                if await !notifications.requestAuthorization() {
                                    settings.notificationsEnabled = false
                                }
                            }
                        }
                    }
                LabeledContent("Low alert", value: settings.useMmol ? "3.9 mmol/L" : "70 mg/dL")
                LabeledContent("High alert", value: settings.useMmol ? "10.0 mmol/L" : "180 mg/dL")
            }

            Section {
                Toggle("Save to Apple Health", isOn: Bindable(settings).healthKitEnabled)
                    .onChange(of: settings.healthKitEnabled) { _, enabled in
                        if enabled {
                            Task {
                                if await healthKit.requestAuthorization() {
                                    await healthKit.export(sync.store.readings)
                                } else {
                                    settings.healthKitEnabled = false
                                }
                            }
                        }
                    }
            } footer: {
                Text("Readings are saved as blood glucose samples.")
            }

            Section("Device") {
                deviceStatusRow
                if settings.deviceConfigured {
                    NavigationLink("Device display settings") {
                        DeviceSettingsView(settings: settings, device: device)
                    }
                }
                Button(settings.deviceConfigured ? "Set up again" : "Set up GlucoBit") {
                    showSetupWizard = true
                }
            }

            Section("Dexcom Account") {
                NavigationLink("Dexcom credentials") {
                    DexcomAccountView(sync: sync)
                }
            }
        }
        .navigationTitle("Settings")
        .scrollContentBackground(.hidden)
        .background(AppTheme.background)
        .tint(AppTheme.accent)
        .sheet(isPresented: $showSetupWizard) {
            SetupWizardView(device: device, settings: settings, sync: sync)
        }
    }

    @ViewBuilder
    private var deviceStatusRow: some View {
        switch device.connectionState {
        case .connected:
            if let status = device.deviceStatus {
                LabeledContent("Status") {
                    HStack(spacing: 6) {
                        Image(systemName: status.wifiConnected ? "checkmark.circle.fill" : "wifi.slash")
                            .foregroundStyle(status.wifiConnected ? AppTheme.positive : AppTheme.warning)
                        Text(status.wifiConnected ? "Online (WiFi)" : "Connected (no WiFi)")
                    }
                }
                LabeledContent("Firmware", value: status.firmwareVersion)
                if let battery = status.batteryPercent {
                    LabeledContent("Battery", value: "\(battery)%")
                }
            } else {
                LabeledContent("Status", value: "Connected")
            }
        case .connecting:
            LabeledContent("Status", value: "Connecting…")
        case .scanning:
            LabeledContent("Status", value: "Scanning…")
        case .disconnected:
            LabeledContent("Status", value: "Not connected")
        case .bluetoothOff:
            LabeledContent("Status", value: "Bluetooth is off")
        }
    }
}

struct DexcomAccountView: View {
    let sync: GlucoseSyncService

    @Environment(\.dismiss) private var dismiss
    @State private var username = KeychainStore.get(.dexcomUsername) ?? ""
    @State private var password = KeychainStore.get(.dexcomPassword) ?? ""
    @State private var server = KeychainStore.get(.dexcomServer) ?? "shareous1.dexcom.com"
    @State private var saving = false
    @State private var error: String?

    var body: some View {
        Form {
            Section {
                TextField("Username", text: $username)
                    .textInputAutocapitalization(.never)
                    .autocorrectionDisabled()
                SecureField("Password", text: $password)
                Picker("Region", selection: $server) {
                    Text("Outside US").tag("shareous1.dexcom.com")
                    Text("United States").tag("share2.dexcom.com")
                }
            }
            if let error {
                Section {
                    Label(error, systemImage: "xmark.octagon")
                        .foregroundStyle(.red)
                }
            }
        }
        .navigationTitle("Dexcom Account")
        .scrollContentBackground(.hidden)
        .background(AppTheme.background)
        .tint(AppTheme.accent)
        .toolbar {
            ToolbarItem(placement: .confirmationAction) {
                if saving {
                    ProgressView()
                } else {
                    Button("Save") { save() }
                        .disabled(username.isEmpty || password.isEmpty)
                }
            }
        }
    }

    private func save() {
        saving = true
        error = nil
        Task {
            do {
                try await sync.client.validateCredentials(
                    .init(username: username, password: password, server: server)
                )
                KeychainStore.set(username, for: .dexcomUsername)
                KeychainStore.set(password, for: .dexcomPassword)
                KeychainStore.set(server, for: .dexcomServer)
                await sync.reloadCredentials()
                await sync.sync(force: true)
                saving = false
                dismiss()
            } catch {
                saving = false
                self.error = error.localizedDescription
            }
        }
    }
}
