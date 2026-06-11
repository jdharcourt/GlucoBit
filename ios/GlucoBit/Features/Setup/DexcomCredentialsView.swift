import SwiftUI

struct DexcomCredentialsView: View {
    @Binding var username: String
    @Binding var password: String
    @Binding var server: String
    @Binding var displayName: String
    let sync: GlucoseSyncService
    let onValidated: () -> Void

    @State private var validating = false
    @State private var validationError: String?

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
            } header: {
                Text("Dexcom Share Account")
            } footer: {
                Text("Use the Dexcom account that has Share enabled. The app verifies the login before sending it to your GlucoBit.")
            }

            Section("Display") {
                TextField("Name shown on device", text: $displayName)
            }

            if let validationError {
                Section {
                    Label(validationError, systemImage: "xmark.octagon")
                        .foregroundStyle(.red)
                }
            }
        }
        .navigationTitle("Dexcom Account")
        .toolbar {
            ToolbarItem(placement: .confirmationAction) {
                if validating {
                    ProgressView()
                } else {
                    Button("Verify & Continue") { validate() }
                        .disabled(username.isEmpty || password.isEmpty)
                }
            }
        }
    }

    private func validate() {
        validating = true
        validationError = nil
        let creds = DexcomShareClient.Credentials(
            username: username, password: password, server: server
        )
        Task {
            do {
                try await sync.client.validateCredentials(creds)
                validating = false
                onValidated()
            } catch {
                validating = false
                validationError = error.localizedDescription
            }
        }
    }
}
