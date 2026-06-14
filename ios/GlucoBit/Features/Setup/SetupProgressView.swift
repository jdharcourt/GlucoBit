import SwiftUI

struct SetupProgressView: View {
    let device: any DeviceManaging
    let payload: [SettingsProvisioner.SettingsKey: Any]
    let onComplete: () -> Void

    enum Phase: Equatable {
        case sending
        case waitingForWifi
        case done
        case failed(String)
    }

    @State private var phase: Phase = .sending
    @State private var wifiWaitTask: Task<Void, Never>?

    var body: some View {
        VStack(spacing: 16) {
            switch phase {
            case .sending:
                ProgressView()
                    .controlSize(.large)
                    .tint(AppTheme.accent)
                Text("Sending settings to your GlucoBit…")
                    .font(.headline)
                    .foregroundStyle(AppTheme.text)

            case .waitingForWifi:
                ProgressView()
                    .controlSize(.large)
                    .tint(AppTheme.accent)
                Text("Waiting for WiFi")
                    .font(.headline)
                    .foregroundStyle(AppTheme.text)
                Text("Settings were received. The device is joining the network.")
                    .font(.subheadline)
                    .foregroundStyle(AppTheme.secondaryText)
                    .multilineTextAlignment(.center)

            case .done:
                Image(systemName: "checkmark.circle.fill")
                    .font(.system(size: 44))
                    .foregroundStyle(AppTheme.positive)
                Text("Your GlucoBit is online!")
                    .font(.headline)
                    .foregroundStyle(AppTheme.text)
                Button("Finish") { onComplete() }
                    .buttonStyle(.borderedProminent)

            case .failed(let message):
                Image(systemName: "xmark.octagon.fill")
                    .font(.system(size: 44))
                    .foregroundStyle(AppTheme.danger)
                Text(message)
                    .font(.subheadline)
                    .foregroundStyle(AppTheme.text)
                    .multilineTextAlignment(.center)
                Button("Try Again") { start() }
                    .buttonStyle(.borderedProminent)
            }
        }
        .padding(20)
        .frame(maxWidth: .infinity)
        .background(AppTheme.surface)
        .clipShape(RoundedRectangle(cornerRadius: AppTheme.radius))
        .overlay {
            RoundedRectangle(cornerRadius: AppTheme.radius)
                .stroke(AppTheme.border, lineWidth: 1)
        }
        .padding(16)
        .frame(maxWidth: .infinity, maxHeight: .infinity)
        .background(AppTheme.background)
        .tint(AppTheme.accent)
        .navigationTitle("Setting Up")
        .navigationBarBackButtonHidden(phase == .sending || phase == .waitingForWifi)
        .onAppear { start() }
        .onDisappear { wifiWaitTask?.cancel() }
        .onChange(of: device.deviceStatus?.wifiConnected) { _, connected in
            if phase == .waitingForWifi, connected == true {
                wifiWaitTask?.cancel()
                phase = .done
            }
        }
    }

    private func start() {
        phase = .sending
        Task {
            do {
                try await SettingsProvisioner(device: device).send(payload)
                phase = .waitingForWifi
                startWifiTimeout()
            } catch {
                phase = .failed("Couldn't send settings: \(error.localizedDescription)")
            }
        }
    }

    private func startWifiTimeout() {
        wifiWaitTask = Task {
            try? await Task.sleep(for: .seconds(45))
            guard !Task.isCancelled, phase == .waitingForWifi else { return }
            if device.deviceStatus?.wifiConnected == true {
                phase = .done
            } else {
                phase = .failed("The device saved the settings but couldn't join \"\(payload[.wifiSSID] ?? "")\". Double-check the WiFi password and try again.")
            }
        }
    }
}
