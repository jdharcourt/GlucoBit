import Foundation

/// Dexcom trend direction. Raw string values match the Dexcom Share API
/// `Trend` field and the firmware's icon/glyph table keys; `code` matches
/// the u8 trend codes in the BLE Glucose Push characteristic.
enum TrendDirection: String, Codable, CaseIterable {
    case none = "None"
    case doubleUp = "DoubleUp"
    case singleUp = "SingleUp"
    case fortyFiveUp = "FortyFiveUp"
    case flat = "Flat"
    case fortyFiveDown = "FortyFiveDown"
    case singleDown = "SingleDown"
    case doubleDown = "DoubleDown"
    case notComputable = "NotComputable"
    case rateOutOfRange = "RateOutOfRange"

    init(dexcomString: String) {
        // Older Share servers return "NonComputable"
        if dexcomString == "NonComputable" {
            self = .notComputable
        } else {
            self = TrendDirection(rawValue: dexcomString) ?? .none
        }
    }

    var code: UInt8 {
        switch self {
        case .none: return 0
        case .doubleUp: return 1
        case .singleUp: return 2
        case .fortyFiveUp: return 3
        case .flat: return 4
        case .fortyFiveDown: return 5
        case .singleDown: return 6
        case .doubleDown: return 7
        case .notComputable: return 8
        case .rateOutOfRange: return 9
        }
    }

    init(code: UInt8) {
        self = TrendDirection.allCases.first { $0.code == code } ?? .none
    }

    /// SF Symbol used in the app UI and widget.
    var symbolName: String {
        switch self {
        case .doubleUp: return "chevron.up.2"
        case .singleUp: return "arrow.up"
        case .fortyFiveUp: return "arrow.up.right"
        case .flat: return "arrow.right"
        case .fortyFiveDown: return "arrow.down.right"
        case .singleDown: return "arrow.down"
        case .doubleDown: return "chevron.down.2"
        case .notComputable, .rateOutOfRange, .none: return "exclamationmark.triangle"
        }
    }

    /// Short text shown in the TREND card, mirroring the device's glyph table.
    var displayText: String {
        switch self {
        case .doubleUp: return "Rising fast"
        case .singleUp: return "Rising"
        case .fortyFiveUp: return "Slowly rising"
        case .flat: return "Steady"
        case .fortyFiveDown: return "Slowly falling"
        case .singleDown: return "Falling"
        case .doubleDown: return "Falling fast"
        case .notComputable, .rateOutOfRange: return "Unknown"
        case .none: return "—"
        }
    }
}
