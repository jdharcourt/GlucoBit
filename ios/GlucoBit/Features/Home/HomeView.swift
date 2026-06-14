import SwiftUI

struct HomeView: View {
    let settings: AppSettings
    let sync: GlucoseSyncService
    let device: any DeviceManaging
    let relay: GlucoseRelay

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 16) {
                Text("Current reading")
                    .font(.title2.weight(.semibold))
                    .foregroundStyle(AppTheme.text)
                deviceBanner
                HeroCardView(
                    reading: sync.store.latest,
                    deltaMgdl: sync.store.deltaMgdl,
                    displayName: settings.displayName,
                    backgroundColorHex: settings.backgroundColorHex,
                    useMmol: settings.useMmol,
                    alertLowMgdl: settings.alertLowMgdl,
                    alertHighMgdl: settings.alertHighMgdl
                )
                HistoryChartView(
                    readings: sync.store.readings,
                    useMmol: settings.useMmol,
                    backgroundColorHex: settings.backgroundColorHex,
                    alertLowMgdl: settings.alertLowMgdl,
                    alertHighMgdl: settings.alertHighMgdl
                )
                if case .failed(let message) = sync.state {
                    Label(message, systemImage: "wifi.exclamationmark")
                        .font(.footnote)
                        .foregroundStyle(AppTheme.warning)
                        .padding(12)
                        .frame(maxWidth: .infinity, alignment: .leading)
                        .background(AppTheme.inset)
                        .clipShape(RoundedRectangle(cornerRadius: AppTheme.radius))
                        .overlay {
                            RoundedRectangle(cornerRadius: AppTheme.radius)
                                .stroke(AppTheme.border, lineWidth: 1)
                        }
                }
            }
            .padding(.horizontal, 16)
            .padding(.vertical, 20)
        }
        .background(AppTheme.background.ignoresSafeArea())
        .refreshable {
            await sync.sync(force: true)
        }
    }

    @ViewBuilder
    private var deviceBanner: some View {
        if settings.deviceConfigured {
            switch device.connectionState {
            case .connected:
                if let status = device.deviceStatus, !status.wifiConnected {
                    banner(
                        icon: "antenna.radiowaves.left.and.right",
                        text: relayBannerText,
                        color: AppTheme.warning
                    )
                }
            case .bluetoothOff:
                banner(
                    icon: "exclamationmark.triangle",
                    text: "Bluetooth is off. Readings can't be relayed to your GlucoBit.",
                    color: AppTheme.warning
                )
            default:
                EmptyView()
            }
        }
    }

    private var relayBannerText: String {
        switch relay.state {
        case .relaying:
            return "Device WiFi is down. Sending readings over Bluetooth."
        case .lastPush(let date):
            let formatter = RelativeDateTimeFormatter()
            return "Device WiFi is down. Last Bluetooth push \(formatter.localizedString(for: date, relativeTo: Date()))."
        case .failed(let message):
            return "Device WiFi is down. Relay issue: \(message)"
        case .idle:
            return "Device WiFi is down. Readings will relay over Bluetooth."
        }
    }

    private func banner(icon: String, text: String, color: Color) -> some View {
        HStack(spacing: 10) {
            Image(systemName: icon)
                .frame(width: 18)
            Text(text)
                .font(.footnote)
            Spacer(minLength: 0)
        }
        .foregroundStyle(color)
        .padding(12)
        .background(AppTheme.inset)
        .clipShape(RoundedRectangle(cornerRadius: AppTheme.radius))
        .overlay {
            RoundedRectangle(cornerRadius: AppTheme.radius)
                .stroke(color.opacity(0.45), lineWidth: 1)
        }
    }
}
