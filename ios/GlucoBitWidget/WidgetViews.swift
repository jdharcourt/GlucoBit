import SwiftUI
import WidgetKit

/// Mini Theme-1: accent-colored value, trend arrow, status and reading age.
struct SmallGlucoseView: View {
    let entry: GlucoseEntry

    private var status: GlucoseStatus {
        guard let r = entry.reading, !isStale(r) else { return .noData }
        return GlucoseStatus(mgdl: r.valueMgdl)
    }

    private var accent: Color {
        guard let r = entry.reading else { return DeviceTheme.statusNoData }
        return DeviceTheme.accentColor(mgdl: r.valueMgdl)
    }

    private func isStale(_ r: GlucoseReading) -> Bool {
        entry.date.timeIntervalSince(r.date) > 15 * 60
    }

    var body: some View {
        VStack(spacing: 4) {
            Text(status.rawValue)
                .font(DeviceTheme.nunito(size: 10, weight: .semibold))
                .foregroundStyle(DeviceTheme.statusColor(status))
                .tracking(1.0)

            HStack(spacing: 6) {
                Text(entry.reading?.displayValue(mmol: entry.useMmol) ?? "--")
                    .font(DeviceTheme.nunito(size: 38, weight: .medium))
                    .foregroundStyle(accent)
                    .minimumScaleFactor(0.6)
                    .lineLimit(1)
                if let trend = entry.reading?.trend {
                    Image(systemName: trend.symbolName)
                        .font(.system(size: 16, weight: .bold))
                        .foregroundStyle(accent)
                }
            }

            Text(entry.useMmol ? "mmol/L" : "mg/dL")
                .font(DeviceTheme.nunito(size: 10))
                .foregroundStyle(DeviceTheme.secondaryText)

            if let reading = entry.reading {
                Text(reading.date, style: .relative)
                    .font(DeviceTheme.nunito(size: 10))
                    .foregroundStyle(DeviceTheme.secondaryText)
                    .multilineTextAlignment(.center)
            }
        }
        .padding(4)
    }
}

struct CircularGlucoseView: View {
    let entry: GlucoseEntry

    var body: some View {
        ZStack {
            AccessoryWidgetBackground()
            VStack(spacing: 0) {
                Text(entry.reading?.displayValue(mmol: entry.useMmol) ?? "--")
                    .font(.system(size: 20, weight: .semibold, design: .rounded))
                    .minimumScaleFactor(0.6)
                if let trend = entry.reading?.trend {
                    Image(systemName: trend.symbolName)
                        .font(.system(size: 11, weight: .bold))
                }
            }
        }
    }
}

struct RectangularGlucoseView: View {
    let entry: GlucoseEntry

    var body: some View {
        HStack(spacing: 8) {
            VStack(alignment: .leading, spacing: 0) {
                HStack(spacing: 4) {
                    Text(entry.reading?.displayValue(mmol: entry.useMmol) ?? "--")
                        .font(.system(size: 22, weight: .semibold, design: .rounded))
                    if let trend = entry.reading?.trend {
                        Image(systemName: trend.symbolName)
                            .font(.system(size: 13, weight: .bold))
                    }
                }
                if let reading = entry.reading {
                    Text(reading.date, style: .relative)
                        .font(.system(size: 11))
                        .foregroundStyle(.secondary)
                }
            }
            Spacer(minLength: 0)
        }
    }
}
