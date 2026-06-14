# GlucoBit BLE GATT server — companion-app link.
#
# Uses raw _bleio (no adafruit_ble) to keep RAM cost minimal on the
# ESP32-S3-N8 (no PSRAM). Provides:
#   - Settings Transfer (write): chunked JSON provisioning from the app
#   - Glucose Push (write): app relays Dexcom readings when WiFi is down
#   - Control/ACK (notify): acknowledgements back to the app
#   - Device Status (read/notify): wifi/setup/needs-data/alarm flags,
#     battery, reading age, firmware version
#
# GATT schema must stay in sync with ios/GlucoBit/Bluetooth/GlucoBitGATT.swift.

import struct
import time
import json

try:
    import _bleio
except ImportError:
    _bleio = None

_BASE = "C0DE00{:02X}-1B34-4C8A-9F2E-6A4D5B7C8E01"

SERVICE_UUID_BYTES = None  # set on init

# Trend codes <-> Dexcom trend strings used elsewhere in the firmware
TREND_BY_CODE = {
    0: None,
    1: "DoubleUp",
    2: "SingleUp",
    3: "FortyFiveUp",
    4: "Flat",
    5: "FortyFiveDown",
    6: "SingleDown",
    7: "DoubleDown",
    8: "NonComputable",
    9: "RateOutOfRange",
}

# Settings transfer opcodes
_OP_BEGIN = 0x01
_OP_DATA = 0x02
_OP_COMMIT = 0x03

# Control/ACK opcodes
_ACK_SETTINGS = 0x10
_ACK_GLUCOSE = 0x20

# ACK codes
ACK_OK = 0
ACK_CRC = 1
ACK_JSON = 2
ACK_FLASH = 3
ACK_LENGTH = 4


def _crc32(data):
    try:
        from binascii import crc32
        return crc32(data) & 0xFFFFFFFF
    except ImportError:
        # Pure-python fallback (payloads are <1 KB, so speed is fine)
        crc = 0xFFFFFFFF
        for byte in data:
            crc ^= byte
            for _ in range(8):
                crc = (crc >> 1) ^ (0xEDB88320 if crc & 1 else 0)
        return crc ^ 0xFFFFFFFF


class GlucoBitBLE:
    """Polled BLE peripheral. Call poll() from the main loop; incoming writes
    queue inside _bleio PacketBuffers, so nothing is lost while the loop is
    busy (including during the blocking alarm loop)."""

    def __init__(self, on_settings, on_glucose, get_status):
        """
        on_settings(dict) -> bool   apply merged settings; True on success
        on_glucose(value_mgdl, trend_str, ts, prev_value, prev_ts) -> bool
        get_status() -> (flags, battery, reading_age_s, (maj, min, patch))
        """
        if _bleio is None:
            raise RuntimeError("BLE not supported on this CircuitPython build")

        self._on_settings = on_settings
        self._on_glucose = on_glucose
        self._get_status = get_status

        self._rx_buf = bytearray(244)
        self._settings_buf = None
        self._settings_len = 0
        self._settings_crc = 0
        self._settings_written = 0
        self._last_status = None
        self._last_status_notify = 0

        adapter = _bleio.adapter
        adapter.enabled = True

        service_uuid = _bleio.UUID(_BASE.format(0x01))
        self._service = _bleio.Service(service_uuid)

        self._settings_char = _bleio.Characteristic.add_to_service(
            self._service,
            _bleio.UUID(_BASE.format(0x02)),
            properties=_bleio.Characteristic.WRITE,
            read_perm=_bleio.Attribute.NO_ACCESS,
            write_perm=_bleio.Attribute.OPEN,
            max_length=244,
            fixed_length=False,
        )
        self._control_char = _bleio.Characteristic.add_to_service(
            self._service,
            _bleio.UUID(_BASE.format(0x03)),
            properties=_bleio.Characteristic.READ | _bleio.Characteristic.NOTIFY,
            read_perm=_bleio.Attribute.OPEN,
            write_perm=_bleio.Attribute.NO_ACCESS,
            max_length=4,
            fixed_length=True,
        )
        self._glucose_char = _bleio.Characteristic.add_to_service(
            self._service,
            _bleio.UUID(_BASE.format(0x04)),
            properties=_bleio.Characteristic.WRITE,
            read_perm=_bleio.Attribute.NO_ACCESS,
            write_perm=_bleio.Attribute.OPEN,
            max_length=20,
            fixed_length=False,
        )
        self._status_char = _bleio.Characteristic.add_to_service(
            self._service,
            _bleio.UUID(_BASE.format(0x05)),
            properties=_bleio.Characteristic.READ | _bleio.Characteristic.NOTIFY,
            read_perm=_bleio.Attribute.OPEN,
            write_perm=_bleio.Attribute.NO_ACCESS,
            max_length=7,
            fixed_length=True,
        )

        # PacketBuffers queue incoming writes between poll() calls
        self._settings_packets = _bleio.PacketBuffer(
            self._settings_char, buffer_size=8, max_packet_size=244
        )
        self._glucose_packets = _bleio.PacketBuffer(
            self._glucose_char, buffer_size=4, max_packet_size=20
        )

        self._adv_data = self._build_advertisement(service_uuid)
        self._scan_resp = self._build_scan_response()
        self._advertise()

    # ── Advertising ───────────────────────────────────────────────

    def _build_advertisement(self, service_uuid):
        # Flags: LE General Discoverable, BR/EDR not supported
        adv = bytes([0x02, 0x01, 0x06])
        # Complete list of 128-bit service UUIDs (iOS background scans
        # match on this)
        uuid128 = bytes(service_uuid.uuid128)
        adv += bytes([0x11, 0x07]) + uuid128
        return adv

    def _build_scan_response(self):
        name = b"GlucoBit"
        return bytes([len(name) + 1, 0x09]) + name

    def _advertise(self):
        adapter = _bleio.adapter
        try:
            adapter.stop_advertising()
        except Exception:
            pass
        try:
            adapter.start_advertising(
                self._adv_data,
                scan_response=self._scan_resp,
                connectable=True,
                interval=0.2,
            )
        except Exception as e:
            print("BLE advertise failed:", e)

    @property
    def connected(self):
        return _bleio.adapter.connected

    # ── Main-loop hook ────────────────────────────────────────────

    def poll(self):
        """Drain queued writes and handle them. Call every loop iteration."""
        if not self.connected:
            if not _bleio.adapter.advertising:
                self._advertise()
            return

        while True:
            n = self._settings_packets.readinto(self._rx_buf)
            if n == 0:
                break
            self._handle_settings_packet(bytes(self._rx_buf[:n]))

        while True:
            n = self._glucose_packets.readinto(self._rx_buf)
            if n == 0:
                break
            self._handle_glucose_packet(bytes(self._rx_buf[:n]))

    # ── Settings transfer ─────────────────────────────────────────

    def _handle_settings_packet(self, pkt):
        if not pkt:
            return
        op = pkt[0]

        if op == _OP_BEGIN and len(pkt) >= 7:
            self._settings_len = struct.unpack_from("<H", pkt, 1)[0]
            self._settings_crc = struct.unpack_from("<I", pkt, 3)[0]
            self._settings_buf = bytearray(self._settings_len)
            self._settings_written = 0

        elif op == _OP_DATA and self._settings_buf is not None:
            data = pkt[2:]  # skip op + seq
            end = self._settings_written + len(data)
            if end > self._settings_len:
                self._ack(_ACK_SETTINGS, ACK_LENGTH)
                self._settings_buf = None
                return
            self._settings_buf[self._settings_written:end] = data
            self._settings_written = end

        elif op == _OP_COMMIT:
            self._commit_settings()

    def _commit_settings(self):
        buf = self._settings_buf
        self._settings_buf = None
        if buf is None or self._settings_written != self._settings_len:
            self._ack(_ACK_SETTINGS, ACK_LENGTH)
            return
        if _crc32(bytes(buf)) != self._settings_crc:
            self._ack(_ACK_SETTINGS, ACK_CRC)
            return
        try:
            updates = json.loads(bytes(buf))
        except (ValueError, MemoryError):
            self._ack(_ACK_SETTINGS, ACK_JSON)
            return
        try:
            ok = self._on_settings(updates)
        except Exception as e:
            print("BLE settings apply error:", e)
            ok = False
        self._ack(_ACK_SETTINGS, ACK_OK if ok else ACK_FLASH)

    # ── Glucose push ──────────────────────────────────────────────

    def _handle_glucose_packet(self, pkt):
        if len(pkt) < 14:
            self._ack(_ACK_GLUCOSE, ACK_LENGTH)
            return
        ver, value, trend_code, prev_value, ts, prev_ts = struct.unpack_from(
            "<BHBHII", pkt
        )
        if ver != 1:
            self._ack(_ACK_GLUCOSE, ACK_LENGTH)
            return
        trend = TREND_BY_CODE.get(trend_code)
        try:
            ok = self._on_glucose(value, trend, ts, prev_value, prev_ts)
        except Exception as e:
            print("BLE glucose apply error:", e)
            ok = False
        self._ack(_ACK_GLUCOSE, ACK_OK if ok else ACK_FLASH)

    # ── Notifications ─────────────────────────────────────────────

    def _ack(self, op, code, detail=0):
        try:
            self._control_char.value = struct.pack("<BBH", op, code, detail)
        except Exception as e:
            print("BLE ack failed:", e)

    def notify_status(self, force=False):
        """Pack and publish device status. Notifies on change, and every 60s
        while needs_data is set — the periodic notify is what wakes the
        suspended iOS app so it can relay a reading."""
        try:
            flags, battery, age, version = self._get_status()
        except Exception:
            return

        if battery is None:
            battery = 0xFF
        if age is None or age > 0xFFFE:
            age = 0xFFFF

        packed = struct.pack(
            "<BBHBBB", flags & 0xFF, battery & 0xFF, age,
            version[0] & 0xFF, version[1] & 0xFF, version[2] & 0xFF,
        )

        now = time.monotonic()
        needs_data = bool(flags & 0x04)
        heartbeat_due = needs_data and (now - self._last_status_notify >= 30)

        if packed == self._last_status and not force and not heartbeat_due:
            return

        self._last_status = packed
        self._last_status_notify = now
        try:
            self._status_char.value = packed
        except Exception as e:
            print("BLE status notify failed:", e)
