import SwiftUI

struct DeviceSettingsView: View {
    let settings: AppSettings
    let device: any DeviceManaging

    @Environment(\.dismiss) private var dismiss
    @State private var displayName: String
    @State private var theme: Int
    @State private var backgroundColor: Color
    @State private var useMmol: Bool
    @State private var alertLowMgdl: Double
    @State private var alertHighMgdl: Double
    @State private var noDataAlarmEnabled: Bool
    @State private var noDataAlarmMinutes: Double
    @State private var sending = false
    @State private var error: String?

    init(settings: AppSettings, device: any DeviceManaging) {
        self.settings = settings
        self.device = device
        _displayName = State(initialValue: settings.displayName)
        _theme = State(initialValue: settings.deviceUITheme)
        _backgroundColor = State(initialValue: DeviceTheme.backgroundColor(hexString: settings.backgroundColorHex))
        _useMmol = State(initialValue: settings.useMmol)
        _alertLowMgdl = State(initialValue: Double(settings.alertLowMgdl))
        _alertHighMgdl = State(initialValue: Double(settings.alertHighMgdl))
        _noDataAlarmEnabled = State(initialValue: settings.noDataAlarmEnabled)
        _noDataAlarmMinutes = State(initialValue: Double(settings.noDataAlarmMinutes))
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
                sliderRow(title: "Low alert", value: thresholdText(Int(alertLowMgdl))) {
                    Slider(value: $alertLowMgdl, in: 55...120, step: 5)
                }
                sliderRow(title: "High alert", value: thresholdText(Int(alertHighMgdl))) {
                    Slider(value: $alertHighMgdl, in: 120...300, step: 5)
                }
                Toggle("No data alarm", isOn: $noDataAlarmEnabled)
                sliderRow(title: "No data after", value: "\(Int(noDataAlarmMinutes)) min") {
                    Slider(value: $noDataAlarmMinutes, in: 5...60, step: 5)
                        .disabled(!noDataAlarmEnabled)
                }
                .foregroundStyle(noDataAlarmEnabled ? .primary : .secondary)
            }

            Section("Connection") {
                NavigationLink {
                    WifiView(device: device)
                } label: {
                    HStack {
                        Image(systemName: "wifi")
                        Text("Configure WiFi")
                    }
                }
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

    private func sliderRow<Content: View>(title: String, value: String, @ViewBuilder content: () -> Content) -> some View {
        VStack(alignment: .leading, spacing: 8) {
            HStack {
                Text(title)
                Spacer()
                Text(value)
                    .foregroundStyle(.secondary)
            }
            content()
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
        settings.alertLowMgdl = Int(alertLowMgdl)
        settings.alertHighMgdl = Int(alertHighMgdl)
        settings.noDataAlarmEnabled = noDataAlarmEnabled
        settings.noDataAlarmMinutes = Int(noDataAlarmMinutes)
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
                    .alertLowMgdl: Int(alertLowMgdl),
                    .alertHighMgdl: Int(alertHighMgdl),
                    .noDataAlarmEnabled: noDataAlarmEnabled,
                    .noDataAlarmMinutes: Int(noDataAlarmMinutes),
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
