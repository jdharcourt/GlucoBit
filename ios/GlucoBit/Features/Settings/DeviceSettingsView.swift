import SwiftUI

/// Display preferences pushed to the device over BLE as a partial settings
/// update (the device merges keys, so WiFi/Dexcom credentials are untouched).
struct DeviceSettingsView: View {
    let settings: AppSettings
    let device: any DeviceManaging

    @Environment(\.dismiss) private var dismiss
    @State private var displayName: String
    @State private var theme: Int
    @State private var backgroundColor: Color
    @State private var useMmol: Bool
    @State private var sending = false
    @State private var error: String?

    init(settings: AppSettings, device: any DeviceManaging) {
        self.settings = settings
        self.device = device
        _displayName = State(initialValue: settings.displayName)
        _theme = State(initialValue: settings.deviceUITheme)
        _backgroundColor = State(initialValue: DeviceTheme.backgroundColor(hexString: settings.backgroundColorHex))
        _useMmol = State(initialValue: settings.useMmol)
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

            if device.connectionState != .connected {
                Section {
                    Label("Connect to your GlucoBit over Bluetooth to apply changes.",
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
        .toolbar {
            ToolbarItem(placement: .confirmationAction) {
                if sending {
                    ProgressView()
                } else {
                    Button("Apply") { apply() }
                        .disabled(device.connectionState != .connected)
                }
            }
        }
    }

    private func apply() {
        sending = true
        error = nil
        let bgHex = backgroundColor.settingsHexString
        Task {
            do {
                try await SettingsProvisioner(device: device).send([
                    .displayName: displayName,
                    .uiTheme: theme,
                    .backgroundColor: bgHex,
                    .mmol: useMmol,
                ])
                settings.displayName = displayName
                settings.deviceUITheme = theme
                settings.backgroundColorHex = bgHex
                settings.useMmol = useMmol
                sending = false
                dismiss()
            } catch {
                sending = false
                self.error = error.localizedDescription
            }
        }
    }
}
