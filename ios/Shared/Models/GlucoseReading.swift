import Foundation

struct GlucoseReading: Codable, Identifiable, Equatable {
    /// Raw Dexcom value in mg/dL.
    let valueMgdl: Int
    let trend: TrendDirection
    let date: Date

    var id: Date { date }

    var valueMmol: Double {
        (Double(valueMgdl) / 18.0 * 10).rounded() / 10
    }

    func displayValue(mmol: Bool) -> String {
        mmol ? String(format: "%.1f", valueMmol) : String(valueMgdl)
    }

    var age: TimeInterval { Date().timeIntervalSince(date) }

    var isStale: Bool { age > 15 * 60 }
}

enum GlucoseStatus: String {
    case low = "LOW"
    case inRange = "IN RANGE"
    case high = "HIGH"
    case veryHigh = "VERY HIGH"
    case noData = "NO DATA"

    init(mgdl: Int, lowMgdl: Int = 70, highMgdl: Int = 180) {
        let veryHighMgdl = max(250, highMgdl + 70)
        if mgdl < lowMgdl {
            self = .low
        } else if mgdl <= highMgdl {
            self = .inRange
        } else if mgdl < veryHighMgdl {
            self = .high
        } else {
            self = .veryHigh
        }
    }
}
