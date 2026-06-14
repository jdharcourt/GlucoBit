import SwiftUI

struct HeroCardView: View {
    let reading: GlucoseReading?
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
        statusColor
    }

    var body: some View {
        VStack(spacing: 8) {
            HStack {
                HStack(spacing: 8) {
                    Circle()
                        .fill(accent)
                        .frame(width: 8, height: 8)
                    Text("LIVE")
                        .font(.caption.weight(.bold))
                        .foregroundStyle(AppTheme.secondaryText)
                }
                Spacer()
                Text(now, format: .dateTime.hour(.twoDigits(amPM: .omitted)).minute(.twoDigits))
                    .font(.subheadline.monospacedDigit().weight(.semibold))
                    .foregroundStyle(AppTheme.secondaryText)
            }
            .padding(.horizontal, 8)

            gauge
                .frame(maxWidth: .infinity)
                .aspectRatio(1.12, contentMode: .fit)

            HStack(spacing: 8) {
                Text(statusLabel)
                    .font(.subheadline.weight(.heavy))
                    .foregroundStyle(accent)
                Text("·")
                    .foregroundStyle(AppTheme.mutedText)
                Text(reading?.trend.displayText.lowercased() ?? "no trend")
                    .font(.subheadline)
                    .foregroundStyle(AppTheme.secondaryText)
            }
            .padding(.bottom, 4)
        }
        .onReceive(clock) { now = $0 }
    }

    private var gauge: some View {
        GeometryReader { proxy in
            let size = min(proxy.size.width, proxy.size.height)
            let center = CGPoint(x: proxy.size.width / 2, y: proxy.size.height * 0.52)
            let radius = size * 0.41
            let ringRadius = size * 0.49
            let ringWidth = max(18, size * 0.075)
            let angle = valueAngle

            ZStack {
                GaugeArc(startAngle: -135, endAngle: 135)
                    .stroke(Color(hex: 0x39433F), style: StrokeStyle(lineWidth: ringWidth, lineCap: .round))
                    .frame(width: ringRadius * 2, height: ringRadius * 2)
                    .position(center)
                GaugeArc(startAngle: -135, endAngle: angle)
                    .stroke(accent, style: StrokeStyle(lineWidth: ringWidth, lineCap: .round))
                    .frame(width: ringRadius * 2, height: ringRadius * 2)
                    .position(center)
                Circle()
                    .fill(gaugeFill)
                    .shadow(color: .black.opacity(0.35), radius: 10, y: 6)
                    .frame(width: radius * 2, height: radius * 2)
                    .position(center)
                Image(systemName: reading?.trend.symbolName ?? "arrow.right")
                    .font(.system(size: size * 0.13, weight: .heavy))
                    .foregroundStyle(accent)
                    .rotationEffect(.degrees(trendRotation))
                    .position(x: center.x, y: center.y - size * 0.18)
                VStack(spacing: 2) {
                    Text(reading.map { $0.displayValue(mmol: useMmol) } ?? "--")
                        .font(.system(size: size * 0.28, weight: .black, design: .rounded))
                        .foregroundStyle(AppTheme.gaugeInk)
                        .minimumScaleFactor(0.55)
                        .lineLimit(1)
                    Text(useMmol ? "mmol/L" : "mg/dL")
                        .font(.system(size: size * 0.06, weight: .black))
                        .foregroundStyle(AppTheme.gaugeInk)
                }
                .frame(width: radius * 1.55)
                .position(x: center.x, y: center.y + size * 0.08)
            }
        }
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

    private var gaugeFill: Color {
        switch status {
        case .low: return Color(hex: 0xF7CDC3)
        case .high, .veryHigh: return Color(hex: 0xF6E2B8)
        case .inRange, .noData: return AppTheme.gauge
        }
    }

    private var valueAngle: Double {
        guard let reading else { return -135 }
        let mmol = max(2, min(22, Double(reading.valueMgdl) / 18.0))
        return -135 + ((mmol - 2) / 20) * 270
    }

    private var trendRotation: Double {
        guard let trend = reading?.trend else { return 0 }
        switch trend {
        case .doubleUp: return -45
        case .singleUp, .fortyFiveUp: return -22
        case .flat: return 0
        case .fortyFiveDown, .singleDown: return 22
        case .doubleDown: return 45
        case .none, .notComputable, .rateOutOfRange: return 0
        }
    }

}

private struct GaugeArc: Shape {
    let startAngle: Double
    let endAngle: Double

    func path(in rect: CGRect) -> Path {
        var path = Path()
        let radius = min(rect.width, rect.height) / 2
        let center = CGPoint(x: rect.midX, y: rect.midY)
        path.addArc(
            center: center,
            radius: radius,
            startAngle: .degrees(startAngle - 90),
            endAngle: .degrees(endAngle - 90),
            clockwise: false
        )
        return path
    }
}



#Preview {
    VStack {
        HeroCardView(
            reading: GlucoseReading(valueMgdl: 102, trend: .flat, date: .now),
            useMmol: true,
            alertLowMgdl: 70,
            alertHighMgdl: 180
        )
        HeroCardView(
            reading: GlucoseReading(valueMgdl: 64, trend: .singleDown, date: .now),
            useMmol: false,
            alertLowMgdl: 70,
            alertHighMgdl: 180
        )
    }
    .padding()
}
