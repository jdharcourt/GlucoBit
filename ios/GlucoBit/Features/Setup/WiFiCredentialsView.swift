import SwiftUI

struct WiFiCredentialsView: View {
    @Binding var ssid: String
    @Binding var password: String
    let onNext: () -> Void

    var body: some View {
        Form {
            Section {
                TextField("Network name (SSID)", text: $ssid)
                    .textInputAutocapitalization(.never)
                    .autocorrectionDisabled()
                SecureField("Password", text: $password)
            } header: {
                Text("Home WiFi")
            } footer: {
                Text("Enter the 2.4 GHz WiFi network your GlucoBit should use. The credentials are sent directly to the device over Bluetooth.")
            }
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
