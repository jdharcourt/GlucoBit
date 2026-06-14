import SwiftUI

struct HeroCardView: View {
    let reading: GlucoseReading?
    let deltaMgdl: Int?
    let displayName: String
    let backgroundColorHex: String
    let useMmol: Bool
    let alertLowMgdl: Int
    let alertHighMgdl: Int

    @State private var now = Date()
    private let clock = Timer.publish(every: 1, on: .main, in: .common).autoconnect()

    private var status: GlucoseStatus {
        guard let reading, !reading.isStale else { return .noData }
        return GlucoseStatus(mgdl: reading.valueMgdl, lowMgdl: alertLowMgdl, highMgdl: alertHighMgdl)
    }

    private var accent: Color {
        guard let reading else { return DeviceTheme.statusNoData }
        return DeviceTheme.accentColor(mgdl: reading.valueMgdl)
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 18) {
            HStack(alignment: .firstTextBaseline) {
                Text(displayName.isEmpty ? "GlucoBit" : displayName)
                    .font(.headline)
                    .foregroundStyle(AppTheme.text)
                Spacer()
                Text(now, format: .dateTime.hour(.twoDigits(amPM: .omitted)).minute(.twoDigits))
                    .font(.subheadline.monospacedDigit())
                    .foregroundStyle(AppTheme.secondaryText)
            }

            HStack(alignment: .lastTextBaseline, spacing: 10) {
                Text(reading.map { $0.displayValue(mmol: useMmol) } ?? "--")
                    .font(.system(size: 72, weight: .semibold, design: .rounded))
                    .foregroundStyle(accent)
                    .minimumScaleFactor(0.5)
                    .lineLimit(1)
                Text(useMmol ? "mmol/L" : "mg/dL")
                    .font(.callout)
                    .foregroundStyle(AppTheme.secondaryText)
            }

            VStack(spacing: 0) {
                readingRow("Status", statusLabel, color: statusColor)
                Divider().overlay(AppTheme.border)
                readingRow("Trend", reading?.trend.displayText ?? "No trend", color: accent, icon: reading?.trend.symbolName ?? "minus")
                Divider().overlay(AppTheme.border)
                readingRow("Delta", deltaText, color: deltaColor)
                if let reading, reading.isStale {
                    Divider().overlay(AppTheme.border)
                    readingRow("Updated", reading.date.formatted(.relative(presentation: .named)), color: AppTheme.mutedText)
                }
            }
            .background(AppTheme.inset)
            .clipShape(RoundedRectangle(cornerRadius: AppTheme.radius))
            .overlay {
                RoundedRectangle(cornerRadius: AppTheme.radius)
                    .stroke(AppTheme.border, lineWidth: 1)
            }
        }
        .padding(16)
        .background(AppTheme.surface)
        .clipShape(RoundedRectangle(cornerRadius: AppTheme.radius))
        .overlay {
            RoundedRectangle(cornerRadius: AppTheme.radius)
                .stroke(AppTheme.border, lineWidth: 1)
        }
        .onReceive(clock) { now = $0 }
    }

    private var statusLabel: String {
        switch status {
        case .low: return "Low"
        case .inRange: return "In range"
        case .high: return "High"
        case .veryHigh: return "Very high"
        case .noData: return "No data"
        }
    }

    private var statusColor: Color {
        switch status {
        case .low: return AppTheme.danger
        case .inRange: return AppTheme.positive
        case .high, .veryHigh: return AppTheme.warning
        case .noData: return AppTheme.mutedText
        }
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
        guard let deltaMgdl else { return AppTheme.mutedText }
        if deltaMgdl < 0 { return AppTheme.positive }
        if deltaMgdl > 0 { return AppTheme.warning }
        return AppTheme.secondaryText
    }

    private func readingRow(_ title: String, _ value: String, color: Color, icon: String? = nil) -> some View {
        HStack(spacing: 10) {
            Text(title)
                .font(.subheadline)
                .foregroundStyle(AppTheme.secondaryText)
            Spacer()
            if let icon {
                Image(systemName: icon)
                    .font(.subheadline.weight(.semibold))
            }
            Text(value)
                .font(.subheadline.weight(.medium))
        }
        .foregroundStyle(color)
        .padding(.horizontal, 12)
        .frame(height: 44)
    }
}

#Preview {
    VStack {
        HeroCardView(
            reading: GlucoseReading(valueMgdl: 102, trend: .flat, date: .now),
            deltaMgdl: -3,
            displayName: "Josh",
            backgroundColorHex: "#070B18",
            useMmol: true,
            alertLowMgdl: 70,
            alertHighMgdl: 180
        )
        HeroCardView(
            reading: GlucoseReading(valueMgdl: 64, trend: .singleDown, date: .now),
            deltaMgdl: -12,
            displayName: "Josh",
            backgroundColorHex: "#070B18",
            useMmol: false,
            alertLowMgdl: 70,
            alertHighMgdl: 180
        )
    }
    .padding()
}
