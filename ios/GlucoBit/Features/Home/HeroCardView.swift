import SwiftUI

/// SwiftUI recreation of the device's Theme 1 (card-based) layout:
/// header strip with name + clock, accent divider, large glucose card,
/// and TREND / DELTA cards below.
struct HeroCardView: View {
    let reading: GlucoseReading?
    let deltaMgdl: Int?
    let displayName: String
    let backgroundColorHex: String
    let useMmol: Bool

    @State private var now = Date()
    private let clock = Timer.publish(every: 1, on: .main, in: .common).autoconnect()

    private var bgColor: Color { DeviceTheme.backgroundColor(hexString: backgroundColorHex) }
    private var lightBg: Color { DeviceTheme.lightened(bgColor) }

    private var status: GlucoseStatus {
        guard let reading, !reading.isStale else { return .noData }
        return GlucoseStatus(mgdl: reading.valueMgdl)
    }

    private var accent: Color {
        guard let reading else { return DeviceTheme.statusNoData }
        return DeviceTheme.accentColor(mgdl: reading.valueMgdl)
    }

    var body: some View {
        VStack(spacing: 0) {
            header
            Rectangle()
                .fill(accent)
                .frame(height: 4)
            VStack(spacing: 10) {
                glucoseCard
                HStack(spacing: 10) {
                    trendCard
                    deltaCard
                }
            }
            .padding(10)
        }
        .background(lightBg)
        .clipShape(RoundedRectangle(cornerRadius: DeviceTheme.cardCornerRadius))
        .onReceive(clock) { now = $0 }
    }

    private var header: some View {
        HStack {
            Text(displayName.isEmpty ? "GlucoBit" : displayName)
                .font(DeviceTheme.nunito(size: 15))
                .foregroundStyle(DeviceTheme.headerText)
            Spacer()
            Text(now, format: .dateTime.hour(.twoDigits(amPM: .omitted)).minute(.twoDigits).second(.twoDigits))
                .font(DeviceTheme.nunito(size: 15))
                .monospacedDigit()
                .foregroundStyle(DeviceTheme.clockText)
        }
        .padding(.horizontal, 14)
        .frame(height: 40)
        .background(bgColor)
    }

    private var glucoseCard: some View {
        VStack(spacing: 2) {
            Text(status.rawValue)
                .font(DeviceTheme.nunito(size: 14, weight: .semibold))
                .foregroundStyle(DeviceTheme.statusColor(status))
                .tracking(1.5)
            Text(reading.map { $0.displayValue(mmol: useMmol) } ?? "--")
                .font(DeviceTheme.nunito(size: 80, weight: .medium))
                .foregroundStyle(accent)
                .minimumScaleFactor(0.5)
                .lineLimit(1)
            Text(useMmol ? "mmol/L" : "mg/dL")
                .font(DeviceTheme.nunito(size: 14))
                .foregroundStyle(DeviceTheme.secondaryText)
            if let reading, reading.isStale {
                Text("Last reading \(reading.date, format: .relative(presentation: .named))")
                    .font(DeviceTheme.nunito(size: 12))
                    .foregroundStyle(DeviceTheme.statusNoData)
            }
        }
        .frame(maxWidth: .infinity)
        .padding(.vertical, 18)
        .background(bgColor)
        .clipShape(RoundedRectangle(cornerRadius: DeviceTheme.cardCornerRadius))
    }

    private var trendCard: some View {
        VStack(alignment: .leading, spacing: 6) {
            Text("TREND")
                .font(DeviceTheme.nunito(size: 11, weight: .semibold))
                .foregroundStyle(DeviceTheme.secondaryText)
                .tracking(1.2)
            HStack {
                Spacer()
                VStack(spacing: 4) {
                    Image(systemName: reading?.trend.symbolName ?? "minus")
                        .font(.system(size: 24, weight: .bold))
                        .foregroundStyle(accent)
                    Text(reading?.trend.displayText ?? "—")
                        .font(DeviceTheme.nunito(size: 13))
                        .foregroundStyle(DeviceTheme.primaryText)
                }
                Spacer()
            }
        }
        .padding(12)
        .frame(maxWidth: .infinity, minHeight: 90)
        .background(bgColor)
        .clipShape(RoundedRectangle(cornerRadius: DeviceTheme.cardCornerRadius))
    }

    private var deltaText: String {
        guard let deltaMgdl else { return "—" }
        if useMmol {
            let mmol = Double(deltaMgdl) / 18.0
            return String(format: "%+.1f", mmol)
        }
        return String(format: "%+d", deltaMgdl)
    }

    private var deltaColor: Color {
        guard let deltaMgdl else { return DeviceTheme.deltaFlat }
        if deltaMgdl < 0 { return DeviceTheme.deltaFalling }
        if deltaMgdl > 0 { return DeviceTheme.deltaRising }
        return DeviceTheme.deltaFlat
    }

    private var deltaCard: some View {
        VStack(alignment: .leading, spacing: 6) {
            Text("DELTA")
                .font(DeviceTheme.nunito(size: 11, weight: .semibold))
                .foregroundStyle(DeviceTheme.secondaryText)
                .tracking(1.2)
            HStack {
                Spacer()
                Text(deltaText)
                    .font(DeviceTheme.nunito(size: 32, weight: .medium))
                    .foregroundStyle(deltaColor)
                Spacer()
            }
            .frame(maxHeight: .infinity)
        }
        .padding(12)
        .frame(maxWidth: .infinity, minHeight: 90)
        .background(bgColor)
        .clipShape(RoundedRectangle(cornerRadius: DeviceTheme.cardCornerRadius))
    }
}

#Preview {
    VStack {
        HeroCardView(
            reading: GlucoseReading(valueMgdl: 102, trend: .flat, date: .now),
            deltaMgdl: -3,
            displayName: "Josh",
            backgroundColorHex: "#070B18",
            useMmol: true
        )
        HeroCardView(
            reading: GlucoseReading(valueMgdl: 64, trend: .singleDown, date: .now),
            deltaMgdl: -12,
            displayName: "Josh",
            backgroundColorHex: "#070B18",
            useMmol: false
        )
    }
    .padding()
}
