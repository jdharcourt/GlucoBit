import Foundation

struct WiFiNetwork: Codable, Equatable, Identifiable {
    var id: String { ssid }
    let ssid: String
    let rssi: Int
}
