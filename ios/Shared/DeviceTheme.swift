import SwiftUI

/// Visual constants ported from the device firmware so the app and widget
/// render glucose in the same style as the GlucoBit display (Theme 1).
enum DeviceTheme {
    // Fixed text colors used by the device's Theme 1.
    static let headerText = Color(hex: 0xDDE7FF)
    static let clockText = Color(hex: 0xEAF1FF)
    static let secondaryText = Color(hex: 0xAFC1E8)
    static let primaryText = Color(hex: 0xDDE7FF)

    static let statusLow = Color(hex: 0xFF4D67)
    static let statusInRange = Color(hex: 0x4DFF88)
    static let statusHigh = Color(hex: 0xFFD34D)
    static let statusVeryHigh = Color(hex: 0xFF8C42)
    static let statusNoData = Color(hex: 0x9AA7C2)

    static let deltaFalling = Color(hex: 0x4DFF88)
    static let deltaRising = Color(hex: 0xFFD34D)
    static let deltaFlat = Color(hex: 0xB9C9EA)

    static let defaultBackgroundHex = "#070B18"
    static let cardCornerRadius: CGFloat = 15

    static func statusColor(_ status: GlucoseStatus) -> Color {
        switch status {
        case .low: return statusLow
        case .inRange: return statusInRange
        case .high: return statusHigh
        case .veryHigh: return statusVeryHigh
        case .noData: return statusNoData
        }
    }

    // Accent color stops from the firmware: (mmol, RGB), linearly interpolated.
    private static let colorStops: [(Double, (Double, Double, Double))] = [
        (3.0, (255, 50, 0)),
        (4.0, (255, 180, 0)),
        (5.0, (0, 180, 0)),
        (7.0, (0, 100, 255)),
        (10.0, (120, 0, 255)),
        (13.0, (80, 0, 120)),
        (15.0, (200, 0, 150)),
    ]

    /// Glucose-level accent color — exact port of the firmware's interpolation.
    static func accentColor(mmol: Double) -> Color {
        let stops = colorStops
        if mmol <= stops[0].0 {
            return Color(rgb: stops[0].1)
        }
        if mmol >= stops[stops.count - 1].0 {
            return Color(rgb: stops[stops.count - 1].1)
        }
        for i in 0..<(stops.count - 1) {
            let (v0, c0) = stops[i]
            let (v1, c1) = stops[i + 1]
            if mmol >= v0 && mmol <= v1 {
                let t = (mmol - v0) / (v1 - v0)
                return Color(rgb: (
                    c0.0 + (c1.0 - c0.0) * t,
                    c0.1 + (c1.1 - c0.1) * t,
                    c0.2 + (c1.2 - c0.2) * t
                ))
            }
        }
        return Color(rgb: stops[stops.count - 1].1)
    }

    static func accentColor(mgdl: Int) -> Color {
        accentColor(mmol: Double(mgdl) / 18.0)
    }

    /// Parse a "#RRGGBB" settings string (BACKGROUND_COLOR).
    static func backgroundColor(hexString: String) -> Color {
        Color(hexString: hexString) ?? Color(hexString: defaultBackgroundHex)!
    }

    /// The firmware's lighten_hex: blend 30% toward white.
    static func lightened(_ color: Color) -> Color {
        let c = UIColor(color)
        var r: CGFloat = 0, g: CGFloat = 0, b: CGFloat = 0, a: CGFloat = 0
        c.getRed(&r, green: &g, blue: &b, alpha: &a)
        return Color(
            red: r + (1 - r) * 0.3,
            green: g + (1 - g) * 0.3,
            blue: b + (1 - b) * 0.3
        )
    }

    static func nunito(size: CGFloat, weight: Font.Weight = .medium) -> Font {
        Font.custom("Nunito", size: size).weight(weight)
    }
}

extension Color {
    init(hex: UInt32) {
        self.init(
            red: Double((hex >> 16) & 0xFF) / 255,
            green: Double((hex >> 8) & 0xFF) / 255,
            blue: Double(hex & 0xFF) / 255
        )
    }

    init(rgb: (Double, Double, Double)) {
        self.init(red: rgb.0 / 255, green: rgb.1 / 255, blue: rgb.2 / 255)
    }

    init?(hexString: String) {
        var s = hexString.trimmingCharacters(in: .whitespaces)
        if s.hasPrefix("#") { s.removeFirst() }
        guard s.count == 6, let value = UInt32(s, radix: 16) else { return nil }
        self.init(hex: value)
    }

    /// Back to "#RRGGBB" for storing in device settings.
    var settingsHexString: String {
        let c = UIColor(self)
        var r: CGFloat = 0, g: CGFloat = 0, b: CGFloat = 0, a: CGFloat = 0
        c.getRed(&r, green: &g, blue: &b, alpha: &a)
        return String(format: "#%02X%02X%02X", Int(r * 255), Int(g * 255), Int(b * 255))
    }
}
