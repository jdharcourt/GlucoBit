# GlucoBit iOS Companion App

SwiftUI companion app for the GlucoBit glucose display. Fetches readings from
the Dexcom Share API, shows them in the device's Theme-1 style with a history
graph, configures the device over Bluetooth, and relays readings to the device
over BLE when its WiFi is down.

## Building

Requirements: Xcode 15+, [XcodeGen](https://github.com/yonaskolb/XcodeGen)
(`brew install xcodegen`).

```sh
cd ios
xcodegen generate          # creates GlucoBit.xcodeproj from project.yml
open GlucoBit.xcodeproj    # build & run from Xcode
```

The `.xcodeproj` is generated and gitignored — `project.yml` is the source of
truth. If `xcodebuild` complains that the active developer directory is
CommandLineTools, run `sudo xcode-select -s /Applications/Xcode.app/Contents/Developer`.

- **Simulator**: everything except real BLE works; the app uses a
  `MockDeviceManager` so the setup wizard and relay UI are testable.
- **Physical iPhone**: required for all real Bluetooth work. With a personal
  (free) team, provisioning profiles last 7 days. If the personal team refuses
  the App Group capability, the widget will show no data — the app itself
  falls back to its Documents directory.

## Architecture

| Component | Role |
|---|---|
| `Shared/` | Models, glucose store, theme — compiled into app **and** widget |
| `Services/DexcomShareClient` | Dexcom Share login + fetch (same API as firmware) |
| `Services/GlucoseSyncService` | Fetch → store → notifications → HealthKit → widget |
| `Bluetooth/DeviceManager` | CoreBluetooth central, state restoration, auto-reconnect |
| `Bluetooth/SettingsProvisioner` | Chunked JSON settings transfer (BEGIN/DATA/COMMIT + CRC32) |
| `Bluetooth/GlucoseRelay` | Pushes readings to the device when it reports `needs_data` |
| `GlucoBitWidget/` | Home screen + lock screen widgets reading the App Group store |

The GATT schema lives in `Bluetooth/GlucoBitGATT.swift` and must stay in sync
with `firmware/app/ble.py`.

## Background relay — what to expect

iOS background execution is restricted; the relay is designed around what is
legitimately possible:

- While the app is **connected** to the device, the device sends a status
  notification every 60 s whenever it needs data. Each notification wakes the
  app (bluetooth-central background mode) long enough to fetch from Dexcom and
  push the reading.
- If the connection drops, a **pending reconnect** stays armed and fires as
  soon as the device advertises again — including while the app is suspended.
  CoreBluetooth **state restoration** revives the app after iOS evicts it.
- **Force-quitting the app stops the relay** until it's reopened. iOS does not
  relaunch force-quit apps for Bluetooth events. The home screen shows a
  banner when relay is impossible (Bluetooth off, etc.).
- `BGAppRefreshTask` runs opportunistically (a few times a day) as a backstop
  to keep the widget and Apple Health fresh.

## Security note

Device provisioning sends WiFi and Dexcom credentials over an unencrypted BLE
connection (CircuitPython's `_bleio` has no practical pairing support). This
is a short-range, one-time transfer to your own device; don't provision in a
place where you don't trust nearby radio listeners.
