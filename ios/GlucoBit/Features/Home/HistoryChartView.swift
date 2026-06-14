import SwiftUI
import Charts

struct HistoryChartView: View {
    let readings: [GlucoseReading]
    let useMmol: Bool
    let backgroundColorHex: String
    let alertLowMgdl: Int
    let alertHighMgdl: Int

    @State private var window: Window = .threeHours

    enum Window: Int, CaseIterable, Identifiable {
        case threeHours = 3
        case sixHours = 6
        case day = 24

        var id: Int { rawValue }
        var label: String {
            switch self {
            case .threeHours: return "3h"
            case .sixHours: return "6h"
            case .day: return "24h"
            }
        }
    }

    private var visibleReadings: [GlucoseReading] {
        let cutoff = Date().addingTimeInterval(-Double(window.rawValue) * 3600)
        return readings.filter { $0.date >= cutoff }
    }

    private func displayValue(_ r: GlucoseReading) -> Double {
        useMmol ? r.valueMmol : Double(r.valueMgdl)
    }

    private var rangeLow: Double { useMmol ? Double(alertLowMgdl) / 18.0 : Double(alertLowMgdl) }
    private var rangeHigh: Double { useMmol ? Double(alertHighMgdl) / 18.0 : Double(alertHighMgdl) }

    private var yDomain: ClosedRange<Double> {
        let values = visibleReadings.map(displayValue(_:))
        let lo = min(values.min() ?? rangeLow, rangeLow)
        let hi = max(values.max() ?? rangeHigh, rangeHigh)
        let pad = useMmol ? 1.0 : 18.0
        return (lo - pad)...(hi + pad)
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 14) {
            HStack {
                Text("History")
                    .font(.headline)
                    .foregroundStyle(AppTheme.text)
                Spacer()
                Picker("Window", selection: $window) {
                    ForEach(Window.allCases) { w in
                        Text(w.label).tag(w)
                    }
                }
                .pickerStyle(.segmented)
                .frame(width: 160)
            }
            .tint(AppTheme.accent)

            if visibleReadings.isEmpty {
                Text("No readings yet")
                    .font(.subheadline)
                    .foregroundStyle(AppTheme.mutedText)
                    .frame(maxWidth: .infinity, minHeight: 180)
            } else {
                chart
                    .frame(height: 200)
            }
        }
        .padding(16)
        .background(AppTheme.surface)
        .clipShape(RoundedRectangle(cornerRadius: AppTheme.radius))
        .overlay {
            RoundedRectangle(cornerRadius: AppTheme.radius)
                .stroke(AppTheme.border, lineWidth: 1)
        }
    }

    private var chart: some View {
        Chart {
            RectangleMark(
                xStart: nil, xEnd: nil,
                yStart: .value("Low", rangeLow),
                yEnd: .value("High", rangeHigh)
            )
            .foregroundStyle(AppTheme.positive.opacity(0.08))

            RuleMark(y: .value("Low threshold", rangeLow))
                .foregroundStyle(AppTheme.danger.opacity(0.45))
                .lineStyle(StrokeStyle(lineWidth: 1, dash: [4, 4]))
            RuleMark(y: .value("High threshold", rangeHigh))
                .foregroundStyle(AppTheme.warning.opacity(0.45))
                .lineStyle(StrokeStyle(lineWidth: 1, dash: [4, 4]))

            ForEach(visibleReadings) { reading in
                PointMark(
                    x: .value("Time", reading.date),
                    y: .value("Glucose", displayValue(reading))
                )
                .foregroundStyle(DeviceTheme.accentColor(mgdl: reading.valueMgdl))
                .symbolSize(window == .day ? 18 : 34)
            }
        }
        .chartYScale(domain: yDomain)
        .chartXAxis {
            AxisMarks(values: .automatic(desiredCount: 4)) { _ in
                AxisGridLine().foregroundStyle(AppTheme.border)
                AxisValueLabel(format: .dateTime.hour().minute())
                    .foregroundStyle(AppTheme.secondaryText)
            }
        }
        .chartYAxis {
            AxisMarks { _ in
                AxisGridLine().foregroundStyle(AppTheme.border)
                AxisValueLabel().foregroundStyle(AppTheme.secondaryText)
            }
        }
    }
}

#Preview {
    let now = Date()
    let readings = (0..<36).map { i in
        GlucoseReading(
            valueMgdl: 100 + Int(40 * sin(Double(i) / 5)),
            trend: .flat,
            date: now.addingTimeInterval(Double(-i) * 300)
        )
    }
    return HistoryChartView(
        readings: readings,
        useMmol: true,
        backgroundColorHex: "#070B18",
        alertLowMgdl: 70,
        alertHighMgdl: 180
    )
        .padding()
}
