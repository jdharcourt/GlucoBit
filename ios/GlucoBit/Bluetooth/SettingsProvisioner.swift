import Foundation

@MainActor
struct SettingsProvisioner {
    let device: any DeviceManaging

    enum SettingsKey: String {
        case wifiSSID = "WIFI_SSID"
        case wifiPassword = "WIFI_PASSWORD"
        case dexcomUsername = "DEXCOM_USERNAME"
        case dexcomPassword = "DEXCOM_PASSWORD"
        case dexcomServer = "DEXCOM_SERVER"
        case displayName = "DISPLAY_NAME"
        case mmol = "MMOL"
        case backgroundColor = "BACKGROUND_COLOR"
        case uiTheme = "UI_THEME"
        case alertLowMgdl = "ALERT_LOW_MGDL"
        case alertHighMgdl = "ALERT_HIGH_MGDL"
        case setupMode = "SETUP_MODE"
    }

    func send(_ settings: [SettingsKey: Any], timeout: TimeInterval = 10) async throws {
        let jsonObject = Dictionary(uniqueKeysWithValues: settings.map { ($0.key.rawValue, $0.value) })
        let json = try JSONSerialization.data(withJSONObject: jsonObject, options: [.sortedKeys])

        try await device.writeSettings(
            GlucoBitGATT.settingsBegin(totalLength: json.count, crc32: json.crc32)
        )

        var sequence: UInt8 = 0
        var offset = 0
        while offset < json.count {
            let end = min(offset + GlucoBitGATT.settingsChunkSize, json.count)
            try await device.writeSettings(
                GlucoBitGATT.settingsData(sequence: sequence, chunk: json[offset..<end])
            )
            sequence &+= 1
            offset = end
        }

        try await device.writeSettings(GlucoBitGATT.settingsCommit)
        try await awaitAck(op: .settingsAck, timeout: timeout)
    }

    func awaitAck(op: GlucoBitGATT.ControlPacket.Op, timeout: TimeInterval) async throws {
        let packets = device.controlPackets
        let result = await withTaskGroup(of: GlucoBitGATT.ControlPacket?.self) { group in
            group.addTask {
                for await packet in packets where packet.op == op {
                    return packet
                }
                return nil
            }
            group.addTask {
                try? await Task.sleep(for: .seconds(timeout))
                return nil
            }
            let first = await group.next() ?? nil
            group.cancelAll()
            return first
        }
        guard let result else { throw DeviceError.ackTimeout }
        guard result.code == .ok else { throw DeviceError.deviceRejected(result.code) }
    }
}
