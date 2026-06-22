# GlucoBit

A CircuitPython glucose monitoring display that fetches readings from the Dexcom Share API and shows them on a colour LCD. Plays audio alarms and flashes an LED when glucose goes out of range.

**Current version:** 1.2.2


##About

GlucoBit is a standalone glucose visualisation and alert device. The product aims to solve some of the daily issues faced by Type 1 Diabetics. At present, CGMs (Continuous Glucose Monitors) send glucose data to a smartphone, where the user can access their current levels and receive alerts for low and high blood sugar events, however, missed hypoglycemic alarms, alarm fatigue, and an over-reliance on smartphones for blood glucose monitoring can cause huge issues for people with type 1 Diabetes.

One of the biggest issues faced with traditional phone-based glucose monitoring is the over-reliance on smartphones. GlucoBit solves this problem by providing a standalone, fully battery-powered device that can travel with you, displaying current glucose levels on an Always-on-display, along with glucose range indicating LEDs. The versatility of GlucoBit allows it to be used anywhere, whether that be on a bedside table, a desk at school or work, or even in an exam situation where phones for glucose monitoring and alerts are not allowed.

Also, smartphone-provided low glucose alerts are often reported to be too quiet and short to effectively alert the user, particularly when sleeping. GlucoBit addresses this problem by providing a louder, persistent alarm that continues until silenced by the user, ensuring they have been alerted to their critical glucose event.


## Hardware

| Component | Details |
|-----------|---------|
| Display | ST7789 SPI, 280×240, rotated 90° |
| Audio | I2S speaker, plays `audio/basic.wav` for alarms |
| Touch | Capacitive sensor on A2 — wake from sleep / silence alarm |
| LED | Neopixel for glucose-level colour feedback |
| Battery | ADC for voltage and percentage |

## Features

- Fetches glucose readings every 90 seconds from the Dexcom cloud API
- Three display themes (card, split-band, minimal)
- Low / high / very-high alarms with audio and LED
- Touch-to-silence alarm
- Web UI for configuration (connect to device IP on port 80)
- Bluetooth setup and settings via the iOS companion app (see [`ios/`](ios/README.md))
- BLE reading relay: the iOS app pushes Dexcom readings to the device when its WiFi is down
- OTA updates via GitHub Releases (checked hourly)
- Deep sleep between fetches to conserve battery

## Alarm Thresholds

| Level | mmol/L | mg/dL |
|-------|--------|-------|
| Low | < 3.9 | < 70 |
| High | > 10.0 | > 180 |
| Very High | > 13.0 | > 250 |

## Setup

1. Flash CircuitPython to your board.
2. Copy all files from this repo to the `CIRCUITPY` drive (excluding `lib/` — install Adafruit libraries separately).
3. Create `settings.json` on the device:

```json
{
  "WIFI_SSID": "your_ssid",
  "WIFI_PASSWORD": "your_password",
  "DEXCOM_USERNAME": "your_dexcom_email",
  "DEXCOM_PASSWORD": "your_dexcom_password",
  "DEXCOM_SERVER": "shareous1.dexcom.com",
  "DISPLAY_NAME": "Name",
  "BACKGROUND_COLOR": "000000",
  "MMOL": true,
  "UI_THEME": 1,
  "SETUP_MODE": false
}
```

> Use `"shareous1.dexcom.com"` for US accounts or `"share2.dexcom.com"` for international.

4. Power on — the device connects to WiFi and starts fetching readings.

## Web UI

Navigate to the device's IP address in a browser to update settings without re-flashing. Changes take effect immediately.

## File Structure

```
firmware/code.py         Entry point
firmware/app/main.py     All application logic
firmware/app/ble.py      BLE GATT server for the iOS companion app
firmware/boot.py         Remounts filesystem read-write on device
firmware/wifi.py         WiFi connection helpers
firmware/ota.py          OTA update system
firmware/audio/          Alarm sound
firmware/icons/          Trend arrow bitmaps
firmware/fonts/          Nunito BDF fonts (30pt, 40pt, 80pt)
hardware/                KiCad PCB design (ESP32-S3-WROOM-1)
ios/                     iOS companion app (SwiftUI) — see ios/README.md
```

BLE requires CircuitPython ≥ 9.0 on the device (`_bleio` on ESP32-S3). On
older builds the firmware logs "BLE unavailable" and runs WiFi-only.

## Filesystem Note

`boot.py` remounts the filesystem read-write for the device, which makes the `CIRCUITPY` drive read-only from the Mac. To write from the Mac (e.g. to edit files), hold the designated GPIO button on boot to skip the remount.

## OTA Updates

Updates are published as GitHub Releases. The device checks for a new version every hour, downloads to `/_update/`, and reboots automatically.

## License

MIT
