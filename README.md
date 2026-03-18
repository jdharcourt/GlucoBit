<meta name="google-site-verification" content="p_6S0dKgn8kSfEV0i6_5-P1h00Iay6jfAAnncVRMXEg" />

# GlucoBit

A low-cost IoT system for non-invasive glucose visualization using Dexcom data on a portable, color-coded display.

## Overview

GlucoBit is a CircuitPython-based device that displays real-time glucose readings from Dexcom continuous glucose monitors (CGMs) on a 280×240 color display. The device features a clear 280x240 LED color display, RGB LED indicators, audio/visual alarms for critical blood sugar events along with battery power and a small form factor for portability.

## Key Features

- **Real-time Glucose Display**: Fetches and displays current glucose readings from Dexcom servers
- **RGB Indicators**: RGB LEDs provide a gradient from red (low) through green (in range) to purple (high), changing based on glucose values
- **Dual Unit Support**: Toggle between mmol/L and mg/dL display modes
- **Low Glucose Alarms**: Configurable alerts with flashing display and audio notification when glucose drops below safe levels
- **Trend Arrows**: Visual indicators showing glucose direction (rising, falling, etc.)
- **Web Configuration**: Web interface for device configuration
- **Battery Power**: Runs fully off battery power, with 3+ Hours of battery life
- **Deep Sleep Mode**: Minimizes power consumption with deep sleep functionality
- **Sound & Alarm**: Loud, persistent alarms that require physical user intervention to silence, ensuring alerts are affective and heard

## Hardware Requirements

GlucoBit runs on **Xiao ESP32 S3/C3** or similar board with:
- 32-bit ARM processor
- WiFi connectivity
- 280×240 pixel color TFT display (ST7789)
- I2S audio output
- NeoPixel LED support
- Touch sensor input
- Multiple GPIO pins for I2S and SPI communication

**Additional Required Components**:
- ST7789 controller-based TFT module
- 2w 8 Ohm Speaker (28mm)
- MAX98357a Audio Amplifier
- 3.7v Li-Po Battery of choice (>500mAh)

**Other Components**
- BMS (Battery Managment System) for 3.7v LiPo (if alternative MCU is used)


## Enclosure 
### Fully 3D-printed enclosure 
- Files available apon request


![ezgif com-video-to-gif-converter](https://github.com/user-attachments/assets/8defc242-e710-4126-b928-75e76a3ea7c8)

<img width="634" height="447" alt="Screenshot 2025-12-27 at 15 15 31" src="https://github.com/user-attachments/assets/ebf19a6d-b33a-4e33-a1de-64fe06652c56" />
Full Body Enclosure 3d model



## Getting Started

### 1. Install CircuitPython

Download and flash the latest CircuitPython firmware for your board - Available from [circuitpython.org](https://circuitpython.org)

### 2. Clone the Repository

Clone this repository to your device's `CIRCUITPY` drive:

```bash
git clone https://github.com/jdharcourt/GlucoBit.git
cd GlucoBit
# Copy all files to CIRCUITPY drive
```

### 3. Install Dependencies - Already Done

All required libraries are included in the `lib/` folder:
- Adafruit ST7789 display driver
- Adafruit HTTP server and requests
- WiFi and network management libraries
- NTP client for time synchronization
- Bitmap font support

### 4. First Power Up + Configuring Settings

Plug device in
The device will start in **AP (Access Point) mode** on first boot:

1. Connect to the WiFi network: **`DexcomConfig`** (password: `config123`)
2. Open a web browser and navigate to the device's IP address
3. Enter your credentials:
   - **WiFi SSID & Password**: Your home network
   - **Dexcom Username & Password**: Your Dexcom account credentials
   - **Dexcom Server**: Leave as Default (**`shareous1.dexcom.com`**(EU)) if located outside of the US, alternatively, change to **`share1.dexcom.com`** if located with the US
   - **Display Name**: (`Optional`) Name your device
   - **Unit**: Toggle mmol/L or mg/dL display
4. Click "Save and Restart"

Settings are saved to `settings.json` on the device.

### 5. Complete Setup

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

- **US**: `share1.dexcom.com`
- **International**: 'shareous1.dexcom.com'

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

### Development

- **Code Structure**: `code.py` contains the main application logic
- **Boot Process**: `boot.py` initializes hardware and storage
- **Testing**: Use `FORCE_ALARM_TEST = True` in `code.py` to test alarms without low glucose or toggle setting on Webpage
- **Memory**: The device has limited RAM; use `gc.collect()` frequently


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


## Support & Documentation

- **CircuitPython Docs**: https://docs.circuitpython.org/
- **Adafruit Libraries**: https://github.com/adafruit/Adafruit_CircuitPython_Bundle
- **Dexcom API**: Unofficial; refer to community documentation and reverse-engineered API examples
- **ESP32-S3 Reference**: https://www.espressif.com/en/products/socs/esp32-s3

## Disclaimer

GlucoBit is not a medical device and should not be used as the sole source for glucose monitoring decisions. Always consult your continuous glucose monitor's official app and follow your healthcare provider's recommendations. This project is for educational and personal monitoring purposes only.

## Authors 

- **Author**: jdharcourt


## Project Status

GlucoBit is an on-going project that is actively being worked on, with a primary focus on the Stripe YSTE competition currently.

---
