import Foundation
import CoreBluetooth
import Observation

struct DiscoveredDevice: Identifiable, Equatable {
    let id: UUID
    let name: String
    let rssi: Int
}

enum DeviceConnectionState: Equatable {
    case bluetoothOff
    case disconnected
    case scanning
    case connecting
    case connected
}

/// Abstraction over the BLE central so the simulator (no CoreBluetooth
/// hardware) can run against MockDeviceManager.
@MainActor
protocol DeviceManaging: AnyObject {
    var connectionState: DeviceConnectionState { get }
    var discoveredDevices: [DiscoveredDevice] { get }
    var deviceStatus: GlucoBitGATT.DeviceStatus? { get }
    var controlPackets: AsyncStream<GlucoBitGATT.ControlPacket> { get }
    /// Invoked when the device signals it needs glucose data (relay trigger).
    var onNeedsData: (() -> Void)? { get set }

    func startScanning()
    func stopScanning()
    func connect(to deviceID: UUID)
    func disconnect()
    func writeSettings(_ data: Data) async throws
    func writeGlucose(_ data: Data) async throws
}

enum DeviceError: LocalizedError {
    case notConnected
    case characteristicMissing
    case writeFailed(String)
    case ackTimeout
    case deviceRejected(GlucoBitGATT.ControlPacket.Code)

    var errorDescription: String? {
        switch self {
        case .notConnected: return "Not connected to a GlucoBit device."
        case .characteristicMissing: return "Device is missing expected Bluetooth characteristics — firmware may be out of date."
        case .writeFailed(let reason): return "Bluetooth write failed: \(reason)"
        case .ackTimeout: return "Device didn't acknowledge in time."
        case .deviceRejected(let code): return "Device rejected the transfer (\(code))."
        }
    }
}

@Observable
@MainActor
final class DeviceManager: NSObject, DeviceManaging {
    private(set) var connectionState: DeviceConnectionState = .disconnected
    private(set) var discoveredDevices: [DiscoveredDevice] = []
    private(set) var deviceStatus: GlucoBitGATT.DeviceStatus?
    var onNeedsData: (() -> Void)?

    let controlPackets: AsyncStream<GlucoBitGATT.ControlPacket>
    private let controlContinuation: AsyncStream<GlucoBitGATT.ControlPacket>.Continuation

    private var central: CBCentralManager!
    private var peripheral: CBPeripheral?
    private var settingsChar: CBCharacteristic?
    private var glucoseChar: CBCharacteristic?
    private var statusChar: CBCharacteristic?
    private var controlChar: CBCharacteristic?
    private var writeContinuation: CheckedContinuation<Void, Error>?
    private var shouldScan = false

    private let settings: AppSettings

    init(settings: AppSettings) {
        self.settings = settings
        (controlPackets, controlContinuation) = AsyncStream.makeStream(
            of: GlucoBitGATT.ControlPacket.self,
            bufferingPolicy: .bufferingNewest(8)
        )
        super.init()
        central = CBCentralManager(
            delegate: self,
            queue: .main,
            options: [
                CBCentralManagerOptionRestoreIdentifierKey: "com.jdharcourt.glucobit.central",
                CBCentralManagerOptionShowPowerAlertKey: true,
            ]
        )
    }

    // MARK: - DeviceManaging

    func startScanning() {
        shouldScan = true
        discoveredDevices = []
        guard central.state == .poweredOn else { return }
        connectionState = .scanning
        central.scanForPeripherals(withServices: [GlucoBitGATT.service])
    }

    func stopScanning() {
        shouldScan = false
        central.stopScan()
        if connectionState == .scanning { connectionState = .disconnected }
    }

    func connect(to deviceID: UUID) {
        guard central.state == .poweredOn,
              let target = central.retrievePeripherals(withIdentifiers: [deviceID]).first else { return }
        central.stopScan()
        settings.pairedDeviceID = deviceID.uuidString
        peripheral = target
        target.delegate = self
        connectionState = .connecting
        // A pending connect never times out and survives backgrounding —
        // it fires whenever the device starts advertising again.
        central.connect(target)
    }

    func disconnect() {
        if let peripheral {
            central.cancelPeripheralConnection(peripheral)
        }
        peripheral = nil
        connectionState = .disconnected
    }

    /// Reconnect to the previously paired device, if any.
    func reconnectIfPaired() {
        guard central.state == .poweredOn,
              connectionState == .disconnected || connectionState == .bluetoothOff,
              let idString = settings.pairedDeviceID,
              let id = UUID(uuidString: idString) else { return }
        connect(to: id)
    }

    func writeSettings(_ data: Data) async throws {
        try await write(data, to: settingsChar)
    }

    func writeGlucose(_ data: Data) async throws {
        try await write(data, to: glucoseChar)
    }

    private func write(_ data: Data, to characteristic: CBCharacteristic?) async throws {
        guard let peripheral, connectionState == .connected else { throw DeviceError.notConnected }
        guard let characteristic else { throw DeviceError.characteristicMissing }
        try await withCheckedThrowingContinuation { (continuation: CheckedContinuation<Void, Error>) in
            writeContinuation = continuation
            peripheral.writeValue(data, for: characteristic, type: .withResponse)
        }
    }
}

extension DeviceManager: CBCentralManagerDelegate {
    nonisolated func centralManagerDidUpdateState(_ central: CBCentralManager) {
        Task { @MainActor in
            switch central.state {
            case .poweredOn:
                if self.shouldScan {
                    self.startScanning()
                } else {
                    self.connectionState = .disconnected
                    self.reconnectIfPaired()
                }
            default:
                self.connectionState = .bluetoothOff
            }
        }
    }

    nonisolated func centralManager(_ central: CBCentralManager, willRestoreState dict: [String: Any]) {
        // iOS relaunched us for a BLE event; re-adopt the restored peripheral.
        let restored = dict[CBCentralManagerRestoredStatePeripheralsKey] as? [CBPeripheral]
        Task { @MainActor in
            if let p = restored?.first {
                self.peripheral = p
                p.delegate = self
                if p.state == .connected {
                    self.connectionState = .connected
                    p.discoverServices([GlucoBitGATT.service])
                }
            }
        }
    }

    nonisolated func centralManager(
        _ central: CBCentralManager,
        didDiscover peripheral: CBPeripheral,
        advertisementData: [String: Any],
        rssi RSSI: NSNumber
    ) {
        let name = (advertisementData[CBAdvertisementDataLocalNameKey] as? String)
            ?? peripheral.name ?? "GlucoBit"
        let device = DiscoveredDevice(id: peripheral.identifier, name: name, rssi: RSSI.intValue)
        Task { @MainActor in
            if let index = self.discoveredDevices.firstIndex(where: { $0.id == device.id }) {
                self.discoveredDevices[index] = device
            } else {
                self.discoveredDevices.append(device)
            }
        }
    }

    nonisolated func centralManager(_ central: CBCentralManager, didConnect peripheral: CBPeripheral) {
        Task { @MainActor in
            self.connectionState = .connected
            peripheral.discoverServices([GlucoBitGATT.service])
        }
    }

    nonisolated func centralManager(
        _ central: CBCentralManager,
        didFailToConnect peripheral: CBPeripheral,
        error: Error?
    ) {
        Task { @MainActor in
            self.connectionState = .disconnected
            self.reconnectIfPaired()
        }
    }

    nonisolated func centralManager(
        _ central: CBCentralManager,
        didDisconnectPeripheral peripheral: CBPeripheral,
        error: Error?
    ) {
        Task { @MainActor in
            self.connectionState = .disconnected
            self.deviceStatus = nil
            self.settingsChar = nil
            self.glucoseChar = nil
            self.statusChar = nil
            self.controlChar = nil
            self.writeContinuation?.resume(throwing: DeviceError.notConnected)
            self.writeContinuation = nil
            // Keep a pending connect outstanding so we reattach the moment
            // the device advertises again (works while backgrounded).
            self.reconnectIfPaired()
        }
    }
}

extension DeviceManager: CBPeripheralDelegate {
    nonisolated func peripheral(_ peripheral: CBPeripheral, didDiscoverServices error: Error?) {
        guard let service = peripheral.services?.first(where: { $0.uuid == GlucoBitGATT.service }) else { return }
        peripheral.discoverCharacteristics(
            [GlucoBitGATT.settingsTransfer, GlucoBitGATT.controlAck,
             GlucoBitGATT.glucosePush, GlucoBitGATT.deviceStatus],
            for: service
        )
    }

    nonisolated func peripheral(
        _ peripheral: CBPeripheral,
        didDiscoverCharacteristicsFor service: CBService,
        error: Error?
    ) {
        let chars = service.characteristics ?? []
        Task { @MainActor in
            for char in chars {
                switch char.uuid {
                case GlucoBitGATT.settingsTransfer: self.settingsChar = char
                case GlucoBitGATT.glucosePush: self.glucoseChar = char
                case GlucoBitGATT.deviceStatus:
                    self.statusChar = char
                    peripheral.setNotifyValue(true, for: char)
                    peripheral.readValue(for: char)
                case GlucoBitGATT.controlAck:
                    self.controlChar = char
                    peripheral.setNotifyValue(true, for: char)
                default:
                    break
                }
            }
        }
    }

    nonisolated func peripheral(
        _ peripheral: CBPeripheral,
        didUpdateValueFor characteristic: CBCharacteristic,
        error: Error?
    ) {
        guard error == nil, let data = characteristic.value else { return }
        let uuid = characteristic.uuid
        Task { @MainActor in
            switch uuid {
            case GlucoBitGATT.deviceStatus:
                if let status = GlucoBitGATT.DeviceStatus(data: data) {
                    self.deviceStatus = status
                    if status.needsData {
                        self.onNeedsData?()
                    }
                }
            case GlucoBitGATT.controlAck:
                if let packet = GlucoBitGATT.ControlPacket(data: data) {
                    self.controlContinuation.yield(packet)
                }
            default:
                break
            }
        }
    }

    nonisolated func peripheral(
        _ peripheral: CBPeripheral,
        didWriteValueFor characteristic: CBCharacteristic,
        error: Error?
    ) {
        Task { @MainActor in
            if let error {
                self.writeContinuation?.resume(throwing: DeviceError.writeFailed(error.localizedDescription))
            } else {
                self.writeContinuation?.resume()
            }
            self.writeContinuation = nil
        }
    }
}

/// Stand-in for the simulator and SwiftUI previews.
@Observable
@MainActor
final class MockDeviceManager: DeviceManaging {
    var connectionState: DeviceConnectionState = .disconnected
    var discoveredDevices: [DiscoveredDevice] = []
    var deviceStatus: GlucoBitGATT.DeviceStatus?
    var onNeedsData: (() -> Void)?

    let controlPackets: AsyncStream<GlucoBitGATT.ControlPacket>
    private let controlContinuation: AsyncStream<GlucoBitGATT.ControlPacket>.Continuation

    init() {
        (controlPackets, controlContinuation) = AsyncStream.makeStream(
            of: GlucoBitGATT.ControlPacket.self,
            bufferingPolicy: .bufferingNewest(8)
        )
    }

    func startScanning() {
        connectionState = .scanning
        Task {
            try? await Task.sleep(for: .seconds(1))
            discoveredDevices = [DiscoveredDevice(id: UUID(), name: "GlucoBit", rssi: -48)]
        }
    }

    func stopScanning() { connectionState = .disconnected }

    func connect(to deviceID: UUID) {
        connectionState = .connecting
        Task {
            try? await Task.sleep(for: .seconds(1))
            connectionState = .connected
            deviceStatus = GlucoBitGATT.DeviceStatus(
                data: Data([0b0001, 87, 30, 0, 1, 2, 2])
            )
        }
    }

    func disconnect() { connectionState = .disconnected }

    func writeSettings(_ data: Data) async throws {
        try? await Task.sleep(for: .milliseconds(100))
        if data.first == GlucoBitGATT.SettingsOp.commit.rawValue {
            controlContinuation.yield(
                GlucoBitGATT.ControlPacket(data: Data([0x10, 0, 0, 0]))!
            )
        }
    }

    func writeGlucose(_ data: Data) async throws {
        try? await Task.sleep(for: .milliseconds(100))
        controlContinuation.yield(
            GlucoBitGATT.ControlPacket(data: Data([0x20, 0, 0, 0]))!
        )
    }
}
