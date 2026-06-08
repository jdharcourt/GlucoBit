# GlucoBit

A CircuitPython glucose monitoring display that fetches readings from the Dexcom Share API and shows them on a colour LCD. Plays audio alarms and flashes an LED when glucose goes out of range.

**Current version:** 1.2.2

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
code.py              Entry point
app/main.py          All application logic
boot.py              Remounts filesystem read-write on device
wifi.py              WiFi connection helpers
ota.py               OTA update system
settings.json        Config (not tracked in git)
audio/basic.wav      Alarm sound
icons/               Trend arrow bitmaps
fonts/               Nunito BDF fonts (30pt, 40pt, 80pt)
lib/                 Adafruit CircuitPython libraries (not tracked in git)
```

## Filesystem Note

`boot.py` remounts the filesystem read-write for the device, which makes the `CIRCUITPY` drive read-only from the Mac. To write from the Mac (e.g. to edit files), hold the designated GPIO button on boot to skip the remount.

## OTA Updates

Updates are published as GitHub Releases. The device checks for a new version every hour, downloads to `/_update/`, and reboots automatically.

## License

MIT
