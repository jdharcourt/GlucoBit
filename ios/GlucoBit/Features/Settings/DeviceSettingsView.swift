import SwiftUI

struct DeviceSettingsView: View {
    let settings: AppSettings
    let device: any DeviceManaging

    @Environment(\.dismiss) private var dismiss
    @State private var displayName: String
    @State private var theme: Int
    @State private var backgroundColor: Color
    @State private var useMmol: Bool
    @State private var alertLowMgdl: Int
    @State private var alertHighMgdl: Int
    @State private var sending = false
    @State private var error: String?
    @State private var wifiSSID = KeychainStore.get(.deviceWifiSSID) ?? ""
    @State private var wifiPassword = KeychainStore.get(.deviceWifiPassword) ?? ""

    init(settings: AppSettings, device: any DeviceManaging) {
        self.settings = settings
        self.device = device
        _displayName = State(initialValue: settings.displayName)
        _theme = State(initialValue: settings.deviceUITheme)
        _backgroundColor = State(initialValue: DeviceTheme.backgroundColor(hexString: settings.backgroundColorHex))
        _useMmol = State(initialValue: settings.useMmol)
        _alertLowMgdl = State(initialValue: settings.alertLowMgdl)
        _alertHighMgdl = State(initialValue: settings.alertHighMgdl)
    }

    var body: some View {
        Form {
            Section("Display") {
                TextField("Name on device", text: $displayName)
                Picker("Theme", selection: $theme) {
                    Text("Cards").tag(1)
                    Text("Bands").tag(2)
                    Text("Minimal").tag(3)
                }
                ColorPicker("Background color", selection: $backgroundColor, supportsOpacity: false)
                Picker("Unit", selection: $useMmol) {
                    Text("mmol/L").tag(true)
                    Text("mg/dL").tag(false)
                }
            }

            Section("Alerts") {
                Stepper("Low alert: \(thresholdText(alertLowMgdl))", value: $alertLowMgdl, in: 55...120, step: 5)
                Stepper("High alert: \(thresholdText(alertHighMgdl))", value: $alertHighMgdl, in: 120...300, step: 5)
            }
            
            
            Section("WiFi") {
                TextField("Network name", text: $wifiSSID)
                    .textInputAutocapitalization(.never)
                    .autocorrectionDisabled()
                SecureField("Password", text: $wifiPassword)
            }

            if device.connectionState != .connected {
                Section {
                    Label("Settings will save in the app. Connect over Bluetooth to push them to GlucoBit.",
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
        .navigationTitle("Device Display")
        .scrollContentBackground(.hidden)
        .background(AppTheme.background)
        .tint(AppTheme.accent)
        .toolbar {
            ToolbarItem(placement: .confirmationAction) {
                if sending {
                    ProgressView()
                } else {
                    Button("Apply") { apply() }
                        .disabled(alertLowMgdl >= alertHighMgdl)
                }
            }
        }
    }

    private func thresholdText(_ mgdl: Int) -> String {
        if useMmol {
            return String(format: "%.1f mmol/L", Double(mgdl) / 18.0)
        }
        return "\(mgdl) mg/dL"
    }

    private func apply() {
        sending = true
        error = nil
        let bgHex = backgroundColor.settingsHexString
        settings.displayName = displayName
        settings.deviceUITheme = theme
        settings.backgroundColorHex = bgHex
        settings.useMmol = useMmol
        settings.alertLowMgdl = alertLowMgdl
        settings.alertHighMgdl = alertHighMgdl
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
                    .displayName: displayName,
                    .uiTheme: theme,
                    .backgroundColor: bgHex,
                    .mmol: useMmol,
                    .alertLowMgdl: alertLowMgdl,
                    .alertHighMgdl: alertHighMgdl,
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
