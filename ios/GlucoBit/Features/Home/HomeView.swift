import SwiftUI

struct HomeView: View {
    let settings: AppSettings
    let sync: GlucoseSyncService
    let device: any DeviceManaging
    let relay: GlucoseRelay

    var body: some View {
        ScrollView {
            VStack(spacing: 14) {
                deviceBanner
                HeroCardView(
                    reading: sync.store.latest,
                    deltaMgdl: sync.store.deltaMgdl,
                    displayName: settings.displayName,
                    backgroundColorHex: settings.backgroundColorHex,
                    useMmol: settings.useMmol
                )
                HistoryChartView(
                    readings: sync.store.readings,
                    useMmol: settings.useMmol,
                    backgroundColorHex: settings.backgroundColorHex
                )
                if case .failed(let message) = sync.state {
                    Label(message, systemImage: "wifi.exclamationmark")
                        .font(.footnote)
                        .foregroundStyle(.orange)
                }
            }
            .padding()
        }
        .background(Color(hex: 0x02050E).ignoresSafeArea())
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
                        color: .orange
                    )
                }
            case .bluetoothOff:
                banner(
                    icon: "exclamationmark.triangle",
                    text: "Bluetooth is off — readings can't be relayed to your GlucoBit.",
                    color: .orange
                )
            default:
                EmptyView()
            }
        }
    }

    private var relayBannerText: String {
        switch relay.state {
        case .relaying:
            return "Device WiFi is down — sending readings over Bluetooth…"
        case .lastPush(let date):
            let formatter = RelativeDateTimeFormatter()
            return "Device WiFi is down — relaying via Bluetooth (last push \(formatter.localizedString(for: date, relativeTo: Date())))."
        case .failed(let message):
            return "Device WiFi is down — relay issue: \(message)"
        case .idle:
            return "Device WiFi is down — readings will be relayed over Bluetooth."
        }
    }

    private func banner(icon: String, text: String, color: Color) -> some View {
        HStack(spacing: 10) {
            Image(systemName: icon)
            Text(text)
                .font(.footnote)
            Spacer(minLength: 0)
        }
        .foregroundStyle(color)
        .padding(12)
        .background(color.opacity(0.12))
        .clipShape(RoundedRectangle(cornerRadius: 12))
    }
}
