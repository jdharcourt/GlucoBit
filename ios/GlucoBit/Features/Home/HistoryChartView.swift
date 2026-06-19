import SwiftUI
import Charts
import CoreHaptics

struct HistoryChartView: View {
    let readings: [GlucoseReading]
    let useMmol: Bool
    let alertLowMgdl: Int
    let alertHighMgdl: Int

    @State private var window: Window = .threeHours
    @State private var selectedReading: GlucoseReading?
    @State private var engine: CHHapticEngine?
    @State private var lastHapticReadingID: Date?

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

    private struct ChartSegment: Identifiable {
        let id = UUID()
        let readings: [GlucoseReading]
        let isStale: Bool
    }

    private var visibleReadings: [GlucoseReading] {
        let cutoff = Date().addingTimeInterval(-Double(window.rawValue) * 3600)
        return readings.filter { $0.date >= cutoff }
    }

    private var chartSegments: [ChartSegment] {
        zip(visibleReadings, visibleReadings.dropFirst()).map { previous, current in
            ChartSegment(
                readings: [previous, current],
                isStale: current.date.timeIntervalSince(previous.date) > 7.5 * 60
            )
        }
    }

    private func displayValue(_ r: GlucoseReading) -> Double {
        useMmol ? r.valueMmol : Double(r.valueMgdl)
    }

    private var rangeLow: Double { useMmol ? Double(alertLowMgdl) / 18.0 : Double(alertLowMgdl) }
    private var rangeHigh: Double { useMmol ? Double(alertHighMgdl) / 18.0 : Double(alertHighMgdl) }

    
    private var xDomain: ClosedRange<Date> {
        let end = Date()
        return end.addingTimeInterval(-Double(window.rawValue) * 3600)...end
    }
    
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
        .onAppear {
            prepareHaptics()
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
                .foregroundStyle(AppTheme.accent.opacity(0.45))
                .lineStyle(StrokeStyle(lineWidth: 1, dash: [2, 4]))
            RuleMark(y: .value("High threshold", rangeHigh))
                .foregroundStyle(AppTheme.accent.opacity(0.45))
                .lineStyle(StrokeStyle(lineWidth: 1, dash: [2, 4]))

            ForEach(chartSegments) { segment in
                ForEach(segment.readings) { reading in
                    LineMark(
                        x: .value("Time", reading.date),
                        y: .value("Glucose", displayValue(reading)),
                        series: .value("Segment", segment.id.uuidString)
                    )
                    .foregroundStyle(AppTheme.chart)
                    .lineStyle(
                        StrokeStyle(
                            lineWidth: 3.4,
                            lineCap: .round,
                            lineJoin: .round,
                            dash: segment.isStale ? [6, 6] : []
                        )
                    )
                    .interpolationMethod(.linear)
                }
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
        .chartXScale(domain: xDomain)
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
                                lastHapticReadingID = nil
                            }
                    )
            }
        }
    }
    
    func prepareHaptics() {
        guard CHHapticEngine.capabilitiesForHardware().supportsHaptics else {
            print("Haptics not supported on this device.")
            return
        }
        
        do {
            engine = try CHHapticEngine()
            engine?.stoppedHandler = { reason in
                print("Haptic engine stopped: \(reason.rawValue)")
                do {
                    try self.engine?.start()
                } catch {
                    print("Failed to restart engine: \(error.localizedDescription)")
                }
            }
            engine?.resetHandler = {
                do {
                    try self.engine?.start()
                } catch {
                    print("Failed to restart engine after reset: \(error.localizedDescription)")
                }
            }
            try engine?.start()
        } catch {
            print("Error creating haptic engine: \(error.localizedDescription)")
        }
    }
    
    func vibrate() {
        guard CHHapticEngine.capabilitiesForHardware().supportsHaptics, let engine = engine else {
            print("Haptics not supported or engine not initialized.")
            return
        }
        
        var events = [CHHapticEvent]()
        let intensity = CHHapticEventParameter(parameterID: .hapticIntensity, value: 1)
        let sharpness = CHHapticEventParameter(parameterID: .hapticSharpness, value: 1)
        let event = CHHapticEvent(eventType: .hapticTransient, parameters: [intensity, sharpness], relativeTime: 0)
        events.append(event)
        
        do {
            let pattern = try CHHapticPattern(events: events, parameters: [])
            let player = try engine.makePlayer(with: pattern)
            try player.start(atTime: 0)
        } catch {
            print("Failed to play pattern: \(error.localizedDescription)")
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
        guard let reading = visibleReadings.min(by: {
            abs($0.date.timeIntervalSince(date)) < abs($1.date.timeIntervalSince(date))
        }) else { return }
        selectedReading = reading
        if lastHapticReadingID != reading.id {
            lastHapticReadingID = reading.id
            vibrate()
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
