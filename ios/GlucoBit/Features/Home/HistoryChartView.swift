import SwiftUI
import Charts

struct HistoryChartView: View {
    let readings: [GlucoseReading]
    let useMmol: Bool
    let alertLowMgdl: Int
    let alertHighMgdl: Int

    @State private var window: Window = .threeHours
    @State private var selectedReading: GlucoseReading?

    enum Window: Int, CaseIterable, Identifiable {
        case hour = 1
        case threeHours = 3
        case twelveHours = 12

        var id: Int { rawValue }
        var label: String {
            switch self {
            case .hour: return "1h"
            case .threeHours: return "3h"
            case .twelveHours: return "12h"
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
        VStack(spacing: 18) {
            if visibleReadings.isEmpty {
                Text("No readings yet")
                    .font(.subheadline)
                    .foregroundStyle(AppTheme.mutedText)
                    .frame(maxWidth: .infinity, maxHeight: .infinity)
            } else {
                chart
                    .frame(maxHeight: .infinity)
            }

            Picker("Window", selection: $window) {
                ForEach(Window.allCases) { w in
                    Text(w.label).tag(w)
                }
            }
            .pickerStyle(.segmented)
            .frame(maxWidth: 260)
            .tint(AppTheme.accent)
        }
        .padding(.horizontal, 8)
        .padding(.bottom, 4)
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
                .foregroundStyle(AppTheme.accent.opacity(0.45))
                .lineStyle(StrokeStyle(lineWidth: 1, dash: [2, 4]))
            RuleMark(y: .value("High threshold", rangeHigh))
                .foregroundStyle(AppTheme.accent.opacity(0.45))
                .lineStyle(StrokeStyle(lineWidth: 1, dash: [2, 4]))

            ForEach(visibleReadings) { reading in
                LineMark(
                    x: .value("Time", reading.date),
                    y: .value("Glucose", displayValue(reading))
                )
                .foregroundStyle(AppTheme.chart)
                .lineStyle(StrokeStyle(lineWidth: 3.4, lineCap: .round, lineJoin: .round))
                .interpolationMethod(.catmullRom)
                AreaMark(
                    x: .value("Time", reading.date),
                    yStart: .value("Baseline", yDomain.lowerBound),
                    yEnd: .value("Glucose", displayValue(reading))
                )
                .foregroundStyle(AppTheme.chart.opacity(0.16))
                .interpolationMethod(.catmullRom)
            }

            if let latest = visibleReadings.last {
                PointMark(
                    x: .value("Time", latest.date),
                    y: .value("Glucose", displayValue(latest))
                )
                .foregroundStyle(statusColor(latest))
                .symbolSize(72)
            }

            if let selectedReading {
                RuleMark(x: .value("Selected time", selectedReading.date))
                    .foregroundStyle(AppTheme.secondaryText.opacity(0.45))
                    .lineStyle(StrokeStyle(lineWidth: 1, dash: [3, 3]))
                PointMark(
                    x: .value("Selected time", selectedReading.date),
                    y: .value("Selected glucose", displayValue(selectedReading))
                )
                .foregroundStyle(statusColor(selectedReading))
                .symbolSize(96)
                .annotation(position: .bottom, spacing: 8) {
                    VStack(spacing: 2) {
                        Text("\(selectedReading.displayValue(mmol: useMmol)) \(useMmol ? "mmol/L" : "mg/dL")")
                            .font(.system(size: 13, weight: .semibold))
                            .foregroundStyle(AppTheme.secondaryText)
                        Text(selectedReading.date, format: .dateTime.hour().minute())
                            .font(.system(size: 11, weight: .medium))
                            .foregroundStyle(AppTheme.secondaryText)
                    }
                    .padding(.horizontal, 10)
                    .padding(.vertical, 7)
                    .background(AppTheme.surface)
                    .clipShape(RoundedRectangle(cornerRadius: 8, style: .continuous))
                    .overlay {
                        RoundedRectangle(cornerRadius: 8, style: .continuous)
                            .stroke(AppTheme.border, lineWidth: 1)
                    }
                }
            }
        }
        .chartYScale(domain: yDomain)
        .chartXAxis {
            AxisMarks(values: .automatic(desiredCount: 4)) { _ in
                AxisGridLine().foregroundStyle(Color.white.opacity(0.07))
                AxisValueLabel(format: .dateTime.hour().minute())
                    .foregroundStyle(AppTheme.secondaryText)
            }
        }
        .chartYAxis {
            AxisMarks { _ in
                AxisGridLine().foregroundStyle(Color.white.opacity(0.07))
                AxisValueLabel().foregroundStyle(AppTheme.secondaryText)
            }
        }
        .chartOverlay { proxy in
            GeometryReader { geometry in
                Rectangle()
                    .fill(.clear)
                    .contentShape(Rectangle())
                    .gesture(
                        DragGesture(minimumDistance: 0)
                            .onChanged { value in
                                selectReading(at: value.location, proxy: proxy, geometry: geometry)
                            }
                            .onEnded { _ in
                                selectedReading = nil
                            }
                    )
            }
        }
    }

    private func statusColor(_ reading: GlucoseReading) -> Color {
        switch GlucoseStatus(mgdl: reading.valueMgdl, lowMgdl: alertLowMgdl, highMgdl: alertHighMgdl) {
        case .low: return AppTheme.danger
        case .high, .veryHigh: return AppTheme.warning
        case .inRange, .noData: return AppTheme.positive
        }
    }

    private func selectReading(at location: CGPoint, proxy: ChartProxy, geometry: GeometryProxy) {
        let frame = geometry[proxy.plotAreaFrame]
        let x = location.x - frame.origin.x
        guard x >= 0, x <= frame.width, let date = proxy.value(atX: x, as: Date.self) else { return }
        selectedReading = visibleReadings.min {
            abs($0.date.timeIntervalSince(date)) < abs($1.date.timeIntervalSince(date))
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
        alertLowMgdl: 70,
        alertHighMgdl: 180
    )
        .padding()
}
