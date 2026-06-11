import Foundation

struct GlucoseReading: Codable, Identifiable, Equatable {
    /// Raw Dexcom value in mg/dL.
    let valueMgdl: Int
    let trend: TrendDirection
    let date: Date

    var id: Date { date }

    /// mmol/L, rounded to 1 dp — same conversion as the firmware (value / 18).
    var valueMmol: Double {
        (Double(valueMgdl) / 18.0 * 10).rounded() / 10
    }

    func displayValue(mmol: Bool) -> String {
        mmol ? String(format: "%.1f", valueMmol) : String(valueMgdl)
    }

    var age: TimeInterval { Date().timeIntervalSince(date) }

    var isStale: Bool { age > 15 * 60 }
}

/// Glucose status bands, with thresholds matching the firmware
/// (low < 3.9 mmol / 70 mg/dL; high > 10.0 / 180; very high > 13.0 / 250).
enum GlucoseStatus: String {
    case low = "LOW"
    case inRange = "IN RANGE"
    case high = "HIGH"
    case veryHigh = "VERY HIGH"
    case noData = "NO DATA"

    init(mgdl: Int) {
        switch mgdl {
        case ..<70: self = .low
        case ..<181: self = .inRange
        case ..<251: self = .high
        default: self = .veryHigh
        }
    }
}
