# GlucoBit

A low-cost IoT system for non-invasive glucose visualization using Dexcom data on a portable, color-coded display.

## Overview

GlucoBit is a CircuitPython-based device that displays real-time glucose readings from Dexcom continuous glucose monitors (CGMs) on a 280×240 color display. The device features intelligent color coding, audio/visual alarms for low glucose levels, battery monitoring, and WiFi configuration—all powered by a microcontroller with minimal power consumption through deep sleep capabilities.

## Key Features

- **Real-time Glucose Display**: Fetches and displays current glucose readings directly from Dexcom servers
- **Intelligent Color Coding**: RGB gradient from red (low) through green (in range) to purple (high) based on glucose values
- **Dual Unit Support**: Toggle between mmol/L and mg/dL display modes
- **Low Glucose Alarms**: Configurable alerts with flashing display and audio notification when glucose drops below safe levels
- **Trend Arrows**: Visual indicators showing glucose direction (rising, falling, flat)
- **Web Configuration**: Easy-to-use web interface for WiFi and Dexcom credentials
- **Battery Monitoring**: Displays remaining battery percentage
- **Deep Sleep Mode**: Minimizes power consumption with touch wake capability
- **NeoPixel Indicators**: RGB LED feedback for glucose status
- **Sound & Alarm**: I2S audio output for alarm notifications

## Hardware Requirements

GlucoBit runs on **Adafruit ESP32-S3 TFT Feather** or compatible board with:
- 32-bit ARM processor
- WiFi connectivity
- 280×240 pixel color TFT display (ST7789)
- I2S audio output
- NeoPixel LED support
- Touch sensor input
- Multiple GPIO pins for I2S and SPI communication

**Recommended display**: ST7789 controller-based TFT module

**Optional**: Audio amplifier and speaker for alarm functionality

## Getting Started

### 1. Install CircuitPython

Download and flash the latest CircuitPython firmware for your board from [circuitpython.org](https://circuitpython.org)

### 2. Clone the Repository

Clone this repository to your device's `CIRCUITPY` drive:

```bash
git clone https://github.com/jdharcourt/GlucoBit.git
cd GlucoBit
# Copy all files to CIRCUITPY drive
```

### 3. Install Dependencies

All required libraries are included in the `lib/` folder:
- Adafruit ST7789 display driver
- Adafruit HTTP server and requests
- WiFi and network management libraries
- NTP client for time synchronization
- Bitmap font support

### 4. Configure Settings

The device will start in **AP (Access Point) mode** on first boot:

1. Connect to the WiFi network: **`DexcomConfig`** (password: `config123`)
2. Open a web browser and navigate to the device's IP address
3. Enter your credentials:
   - **WiFi SSID & Password**: Your home network
   - **Dexcom Username & Password**: Your Dexcom account credentials
   - **Dexcom Server**: Default is `shareous1.dexcom.com` (US) or your region's server
   - **Display Name**: Label for your device
   - **Unit**: Toggle mmol/L or mg/dL display
4. Click "Save and Restart"

Settings are saved to `settings.json` on the device.

### 5. Power On

Once configured, the device will:
1. Connect to your WiFi network
2. Authenticate with Dexcom servers
3. Fetch and display your current glucose reading
4. Update every minute with the latest data

## Usage

### Display Status

- **Main Value**: Large glucose reading (color-coded)
- **Trend Arrow**: Direction of glucose change
- **Time**: Last reading timestamp
- **Battery**: Current battery percentage (bottom right)
- **Status**: IN RANGE / HIGH / LOW / etc.

### Alarm Behavior

When glucose falls below your threshold:
- Display flashes red
- Audio alarm sounds (880 Hz tone)
- Touch the sensor to silence the alarm
- Device remains in wake mode for monitoring

### Sleep Mode

- Device enters deep sleep to conserve battery
- Touch the sensor at any time to wake
- Display turns off; minimal power draw

### Web Interface

Restart the device in AP mode by holding the reset button. The web interface allows you to:
- Update WiFi credentials
- Change Dexcom login information
- Switch glucose units
- Adjust other settings

## Color Scale Reference

The gradient display maps glucose values (mmol/L) to colors:

| Glucose (mmol/L) | Color | Status |
|---|---|---|
| < 3.0 | Bright Red | Critical Low |
| 3.0–4.0 | Red-Orange | Low |
| 4.0–5.0 | Orange-Yellow | Low-Normal |
| 5.0–7.0 | Green | In Range |
| 7.0–10.0 | Blue-Green | In Range |
| 10.0–13.0 | Blue-Purple | High |
| 13.0–15.0 | Purple | Very High |
| > 15.0 | Magenta | Critical High |

## Configuration Options

Edit `settings.json` for advanced configuration:

```json
{
  "WIFI_SSID": "your-network-name",
  "WIFI_PASSWORD": "your-wifi-password",
  "DEXCOM_USERNAME": "your@email.com",
  "DEXCOM_PASSWORD": "your-password",
  "DEXCOM_SERVER": "shareous1.dexcom.com",
  "DISPLAY_NAME": "My GlucoBit",
  "MMOL": true
}
```

## Supported Dexcom Servers

- **US**: `shareous1.dexcom.com`
- **International**: Check your Dexcom app settings for your region's server

## Troubleshooting

### Device won't connect to WiFi
- Verify SSID and password in `settings.json`
- Check that your WiFi is not using special characters
- Reset to AP mode and reconfigure

### No glucose readings displayed
- Verify Dexcom credentials are correct
- Check internet connectivity
- Ensure the Dexcom share has been configured in the Dexcom app
- Review the serial monitor output for API errors

### Alarm not triggering
- Check that your device's audio is properly connected (if hardware installed)
- Verify glucose threshold is below 70 mg/dL (3.9 mmol/L)
- Review `code.py` for alarm threshold configuration

### Display flickering or artifacts
- Ensure all SPI connections are secure
- Check display contrast settings
- Verify power supply provides sufficient current

For detailed debugging, connect via USB and monitor the serial output:

```bash
# On macOS/Linux
ls /dev/tty.* | grep -i usb
# Or use the CircuitPython Serial Monitor in VS Code
```

## Contributing

Contributions are welcome! To get started:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Make your changes
4. Test thoroughly on the device
5. Submit a pull request

### Development Tips

- **Code Structure**: `code.py` contains the main application logic
- **Boot Process**: `boot.py` initializes hardware and storage
- **Testing**: Use `FORCE_ALARM_TEST = True` in `code.py` to test alarms without low glucose
- **Memory**: The device has limited RAM; use `gc.collect()` frequently

## Project Highlights

- **Efficient**: Uses CircuitPython's built-in hardware optimization and deep sleep
- **Portable**: Compact form factor with battery support
- **Extensible**: Built on CircuitPython libraries; easy to add features
- **Open Source**: Community-driven with an MIT License

## Hardware Pinout Reference

| Function | Pin |
|---|---|
| Display Clock (SCK) | D8 |
| Display MOSI | D10 |
| Display Chip Select (CS) | D0 |
| Display Data/Command (DC) | D1 |
| Display Reset | D7 |
| Backlight PWM | D9 |
| I2S Bit Clock | D5 |
| I2S Word Select | D6 |
| I2S Data In | D4 |
| NeoPixel LED | A3 |
| Touch Sensor | A2 |
| Battery ADC | A0/A1 |

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Support & Documentation

- **CircuitPython Docs**: https://docs.circuitpython.org/
- **Adafruit Libraries**: https://github.com/adafruit/Adafruit_CircuitPython_Bundle
- **Dexcom API**: Unofficial; refer to community documentation and reverse-engineered API examples
- **ESP32-S3 Reference**: https://www.espressif.com/en/products/socs/esp32-s3

## Disclaimer

GlucoBit is not a medical device and should not be used as the sole source for glucose monitoring decisions. Always consult your continuous glucose monitor's official app and follow your healthcare provider's recommendations. This project is for educational and personal monitoring purposes only.

## Authors & Contributors

- **Maintainer**: jdharcourt
- **Community**: Open to all contributions and improvements

## Project Status

GlucoBit is actively maintained and welcomes feature requests and bug reports. Check the [Issues](https://github.com/jdharcourt/GlucoBit/issues) tab for known limitations and planned enhancements.

---

**Questions?** Feel free to open an issue or start a discussion on GitHub.
