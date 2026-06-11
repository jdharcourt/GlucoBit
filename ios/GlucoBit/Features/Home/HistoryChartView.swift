import SwiftUI
import Charts

struct HistoryChartView: View {
    let readings: [GlucoseReading]
    let useMmol: Bool
    let backgroundColorHex: String

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

    private var bgColor: Color { DeviceTheme.backgroundColor(hexString: backgroundColorHex) }

    private var visibleReadings: [GlucoseReading] {
        let cutoff = Date().addingTimeInterval(-Double(window.rawValue) * 3600)
        return readings.filter { $0.date >= cutoff }
    }

    private func displayValue(_ r: GlucoseReading) -> Double {
        useMmol ? r.valueMmol : Double(r.valueMgdl)
    }

    // Target range band: 3.9–10 mmol / 70–180 mg/dL, matching the firmware.
    private var rangeLow: Double { useMmol ? 3.9 : 70 }
    private var rangeHigh: Double { useMmol ? 10.0 : 180 }

    private var yDomain: ClosedRange<Double> {
        let values = visibleReadings.map(displayValue(_:))
        let lo = min(values.min() ?? rangeLow, rangeLow)
        let hi = max(values.max() ?? rangeHigh, rangeHigh)
        let pad = useMmol ? 1.0 : 18.0
        return (lo - pad)...(hi + pad)
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack {
                Text("HISTORY")
                    .font(DeviceTheme.nunito(size: 11, weight: .semibold))
                    .foregroundStyle(DeviceTheme.secondaryText)
                    .tracking(1.2)
                Spacer()
                Picker("Window", selection: $window) {
                    ForEach(Window.allCases) { w in
                        Text(w.label).tag(w)
                    }
                }
                .pickerStyle(.segmented)
                .frame(width: 160)
            }

            if visibleReadings.isEmpty {
                Text("No readings yet")
                    .font(DeviceTheme.nunito(size: 14))
                    .foregroundStyle(DeviceTheme.statusNoData)
                    .frame(maxWidth: .infinity, minHeight: 180)
            } else {
                chart
                    .frame(height: 200)
            }
        }
        .padding(14)
        .background(bgColor)
        .clipShape(RoundedRectangle(cornerRadius: DeviceTheme.cardCornerRadius))
    }

    private var chart: some View {
        Chart {
            RectangleMark(
                xStart: nil, xEnd: nil,
                yStart: .value("Low", rangeLow),
                yEnd: .value("High", rangeHigh)
            )
            .foregroundStyle(DeviceTheme.statusInRange.opacity(0.08))

            RuleMark(y: .value("Low threshold", rangeLow))
                .foregroundStyle(DeviceTheme.statusLow.opacity(0.4))
                .lineStyle(StrokeStyle(lineWidth: 1, dash: [4, 4]))
            RuleMark(y: .value("High threshold", rangeHigh))
                .foregroundStyle(DeviceTheme.statusHigh.opacity(0.4))
                .lineStyle(StrokeStyle(lineWidth: 1, dash: [4, 4]))

            ForEach(visibleReadings) { reading in
                PointMark(
                    x: .value("Time", reading.date),
                    y: .value("Glucose", displayValue(reading))
                )
                .foregroundStyle(DeviceTheme.accentColor(mgdl: reading.valueMgdl))
                .symbolSize(window == .day ? 14 : 28)
            }
        }
        .chartYScale(domain: yDomain)
        .chartXAxis {
            AxisMarks(values: .automatic(desiredCount: 4)) { _ in
                AxisGridLine().foregroundStyle(DeviceTheme.secondaryText.opacity(0.15))
                AxisValueLabel(format: .dateTime.hour().minute())
                    .foregroundStyle(DeviceTheme.secondaryText)
            }
        }
        .chartYAxis {
            AxisMarks { _ in
                AxisGridLine().foregroundStyle(DeviceTheme.secondaryText.opacity(0.15))
                AxisValueLabel().foregroundStyle(DeviceTheme.secondaryText)
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
    return HistoryChartView(readings: readings, useMmol: true, backgroundColorHex: "#070B18")
        .padding()
}
