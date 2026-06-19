import Foundation
import CoreBluetooth

/// GATT schema shared with the firmware (firmware/app/ble.py).
/// All multi-byte fields are little-endian.
enum GlucoBitGATT {
    static let service = CBUUID(string: "C0DE0001-1B34-4C8A-9F2E-6A4D5B7C8E01")
    static let settingsTransfer = CBUUID(string: "C0DE0002-1B34-4C8A-9F2E-6A4D5B7C8E01")
    static let controlAck = CBUUID(string: "C0DE0003-1B34-4C8A-9F2E-6A4D5B7C8E01")
    static let glucosePush = CBUUID(string: "C0DE0004-1B34-4C8A-9F2E-6A4D5B7C8E01")
    static let deviceStatus = CBUUID(string: "C0DE0005-1B34-4C8A-9F2E-6A4D5B7C8E01")
    static let wifiScan = CBUUID(string: "C0DE0006-1B34-4C8A-9F2E-6A4D5B7C8E01")

    /// Max JSON bytes per settings DATA chunk (stays under typical iOS MTU).
    static let settingsChunkSize = 160

    // Settings transfer opcodes
    enum SettingsOp: UInt8 {
        case begin = 0x01
        case data = 0x02
        case commit = 0x03
    }

    enum WiFiScanOp: UInt8 {
        case request = 0x30
        case begin = 0x31
        case data = 0x32
        case commit = 0x33
        case error = 0x34
    }

    // Control/ACK packet: op u8, code u8, detail u16
    struct ControlPacket: Equatable {
        enum Op: UInt8 {
            case settingsAck = 0x10
            case glucoseAck = 0x20
        }
        enum Code: UInt8 {
            case ok = 0
            case crcMismatch = 1
            case jsonParseFailed = 2
            case flashWriteFailed = 3
            case lengthMismatch = 4
        }

        let op: Op
        let code: Code
        let detail: UInt16

        init?(data: Data) {
            guard data.count >= 4,
                  let op = Op(rawValue: data[data.startIndex]),
                  let code = Code(rawValue: data[data.startIndex + 1]) else { return nil }
            self.op = op
            self.code = code
            self.detail = UInt16(data[data.startIndex + 2]) | (UInt16(data[data.startIndex + 3]) << 8)
        }
    }

    static func encodeGlucosePush(latest: GlucoseReading, previous: GlucoseReading?) -> Data {
        var data = Data(capacity: 18)
        data.append(2)
        data.appendLE(UInt16(clamping: latest.valueMgdl))
        data.append(latest.trend.code)
        data.appendLE(UInt16(clamping: previous?.valueMgdl ?? latest.valueMgdl))
        data.appendLE(UInt32(latest.date.timeIntervalSince1970))
        data.appendLE(UInt32((previous ?? latest).date.timeIntervalSince1970))
        data.appendLE(UInt32(Date().timeIntervalSince1970))
        return data
    }

    struct DeviceStatus: Equatable {
        let wifiConnected: Bool
        let setupMode: Bool
        let needsData: Bool
        let alarmActive: Bool
        /// 0–100, nil when unavailable (0xFF on the wire).
        let batteryPercent: Int?
        /// Seconds since the device's last reading, nil when none (0xFFFF).
        let readingAgeSeconds: Int?
        let firmwareVersion: String

        init?(data: Data) {
            guard data.count >= 7 else { return nil }
            let b = [UInt8](data)
            wifiConnected = b[0] & 0x01 != 0
            setupMode = b[0] & 0x02 != 0
            needsData = b[0] & 0x04 != 0
            alarmActive = b[0] & 0x08 != 0
            batteryPercent = b[1] == 0xFF ? nil : Int(b[1])
            let age = UInt16(b[2]) | (UInt16(b[3]) << 8)
            readingAgeSeconds = age == 0xFFFF ? nil : Int(age)
            firmwareVersion = "\(b[4]).\(b[5]).\(b[6])"
        }
    }

    static func settingsBegin(totalLength: Int, crc32: UInt32) -> Data {
        var data = Data([SettingsOp.begin.rawValue])
        data.appendLE(UInt16(totalLength))
        data.appendLE(crc32)
        return data
    }

    static func settingsData(sequence: UInt8, chunk: Data) -> Data {
        var data = Data([SettingsOp.data.rawValue, sequence])
        data.append(chunk)
        return data
    }

    static var settingsCommit: Data {
        Data([SettingsOp.commit.rawValue])
    }
}

extension Data {
    mutating func appendLE(_ value: UInt16) {
        append(UInt8(value & 0xFF))
        append(UInt8(value >> 8))
    }

    mutating func appendLE(_ value: UInt32) {
        append(UInt8(value & 0xFF))
        append(UInt8((value >> 8) & 0xFF))
        append(UInt8((value >> 16) & 0xFF))
        append(UInt8((value >> 24) & 0xFF))
    }

    /// Standard CRC-32 (IEEE 802.3), matching Python's binascii.crc32.
    var crc32: UInt32 {
        var crc: UInt32 = 0xFFFFFFFF
        for byte in self {
            crc ^= UInt32(byte)
            for _ in 0..<8 {
                crc = (crc >> 1) ^ (0xEDB88320 & (0 &- (crc & 1)))
            }
        }
        return crc ^ 0xFFFFFFFF
    }
}
