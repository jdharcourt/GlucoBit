import time
import audiobusio
import board
import wifi
import socketpool
import ssl
import displayio
import json
import touchio
import os
import gc
import alarm
from adafruit_display_text import label
import adafruit_st7789
import fourwire
import adafruit_requests
import adafruit_bitmap_font.bitmap_font as bitmap_font
from adafruit_httpserver import Server, Request, Response, MIMETypes
from audiocore import WaveFile
import analogio
import pwmio
import busio
import microcontroller



    
# At the very TOP of your file, after imports
if alarm.sleep_memory[0] == 1:
    print("Woke from deep sleep (touch)")
    alarm.sleep_memory[0] = 0
    
    # CRITICAL: Manually reset touch hardware on wake
    try:
        import touchio
        # Force deinit any lingering touch
        touchio.TouchIn(board.A2).deinit()
    except:
        pass
    
    gc.collect()
    time.sleep(0.5)  # Give hardware time to settle



MIMETypes.configure(default_to="text/plain")


alarm_active = False
alarm_suppressed = False
last_low = None
last_reading = None

last_ssid = None

session = None
web_server = None
previous_glucose = None

FORCE_ALARM_TEST = False

BCLK = board.D5    
LRCLK = board.D6  
DIN = board.D4    
audio = audiobusio.I2SOut(bit_clock=BCLK, word_select=LRCLK, data=DIN)
vbat_pin = analogio.AnalogIn(board.A3)

touch = None
touch_start_time = None

previous_glucose = None

#Initialise Touch
def init_touch():
    global touch
    
    # CRITICAL: Force release of A0 hardware
    max_cleanup_attempts = 5
    for cleanup_attempt in range(max_cleanup_attempts):
        try:
            # Aggressively attempt to deinit any existing touch on A0
            temp = touchio.TouchIn(board.A2)
            temp.deinit()
            del temp
            gc.collect()
            time.sleep(0.1)
            print(f"A2 cleanup attempt {cleanup_attempt + 1} succeeded")
            break
        except Exception as e:
            print(f"A2 cleanup attempt {cleanup_attempt + 1}: {e}")
            gc.collect()
            time.sleep(0.15)
    
    # Now try to create touch with retries
    touch = None
    max_retries = 5
    for attempt in range(max_retries):
        try:
            touch = touchio.TouchIn(board.A2)
            time.sleep(0.2)  # Increased wait time
            touch.threshold = touch.raw_value + 1000
            print(f"Touch initialized on A2 (attempt {attempt + 1})")
            return True
        except Exception as e:
            print(f"Touch init attempt {attempt + 1} failed: {e}")
            if touch:
                try:
                    touch.deinit()
                except:
                    pass
                touch = None
            gc.collect()
            time.sleep(0.2)  # Increased wait between retries
    
    print("WARNING: Failed to initialize touch after all retries")
    touch = None
    return False



def init_hardware():
    global display, display_bus, touch, backlight

    # Re-init display
    displayio.release_displays()
    spi = busio.SPI(clock=board.D8, MOSI=board.D10)
    while not spi.try_lock():
        pass
    spi.configure(baudrate=24000000)
    spi.unlock()

    display_bus = fourwire.FourWire(spi, command=board.D1, chip_select=board.D0, reset=board.D7)
    display = adafruit_st7789.ST7789(
        display_bus, width=280, height=240, rotation=90, colstart=0, rowstart=20
    )
    backlight.duty_cycle = 65535
    
    splash = displayio.Group()
    init_touch()
    



    


# fonts
try:
    font_40 = bitmap_font.load_font("fonts/Nunito-Medium-40.bdf")
    font_30 = bitmap_font.load_font("fonts/Nunito-Medium-30.bdf")
    font_80 = bitmap_font.load_font("fonts/Nunito-Medium-80.bdf")
    font = bitmap_font.load_font("fonts/nunito-75.bdf")
except Exception as e:
    print(f"Font load failed: {e}")
    from terminalio import FONT as font_40  # Fallback 

# config
SETTINGS_FILE = "settings.json"

# Default settings
default_settings = {
    "WIFI_SSID": "F.B.I Surveillance Van",
    "WIFI_PASSWORD": "9conorclune!",
    "DEXCOM_USERNAME": "jdharc",
    "DEXCOM_PASSWORD": "SVCC123!",
    "DEXCOM_SERVER": "shareous1.dexcom.com",
    "DISPLAY_NAME": "DexcomFollowerName",
    "MMOL": True
}


        
# Simple URL decoding function
def url_decode(text):
    """Simple URL decoder for common percent-encoded characters."""
    result = ""
    i = 0
    while i < len(text):
        if text[i] == '%' and i + 2 < len(text):
            try:
                hex_str = text[i + 1:i + 3]
                result += chr(int(hex_str, 16))
                i += 3
            except ValueError:
                result += text[i]
                i += 1
        else:
            result += text[i]
            i += 1
    return result.replace('+', ' ')

# Load settings from file if exists
settings = default_settings.copy()
if SETTINGS_FILE in os.listdir():
    try:
        with open(SETTINGS_FILE, "r") as f:
            loaded_settings = json.load(f)
        # Decode URL-encoded strings in settings
        for key, value in loaded_settings.items():
            if isinstance(value, str):
                loaded_settings[key] = url_decode(value)
        settings.update(loaded_settings)
        print("Loaded settings from file.")
    except Exception as e:
        print(f"Failed to load settings: {e}")

# Extract settings to variables
WIFI_SSID = settings["WIFI_SSID"]
WIFI_PASSWORD = settings["WIFI_PASSWORD"]
DEXCOM_USERNAME = settings["DEXCOM_USERNAME"]
DEXCOM_PASSWORD = settings["DEXCOM_PASSWORD"]
DEXCOM_SERVER = settings["DEXCOM_SERVER"]
DISPLAY_NAME = settings["DISPLAY_NAME"]
MMOL = settings["MMOL"]


tft_cs = board.D0
tft_dc = board.D1
tft_rst = board.D7
backlight = pwmio.PWMOut(board.D9, frequency=1000, duty_cycle=0)

if alarm.wake_alarm:
    backlight.duty_cycle = 65535
    print("awake")



init_hardware()
red_overlay = displayio.Bitmap(display.width, display.height, 1)
red_palette = displayio.Palette(1)
red_palette[0] = 0xFF0000                  # pure red
red_tilegrid = displayio.TileGrid(red_overlay, pixel_shader=red_palette)
    
# Trend arrows location 
TREND_ARROWS = {
    1: "/icons/up.bmp", 2: "/icons/up.bmp", 'Flat': "/icons/level.bin", 
    4: "/icons/down.bmp", 5: "/icons/down.bmp", 6: "/icons/up-right.bmp", 
    7: "/icons/down-right.bmp"
}

def load_rgb565(path, width, height):
    with open(path, "rb") as f:
        bitmap = displayio.Bitmap(width, height, 65536)
        for y in range(height):
            for x in range(width):
                b0 = f.read(1)
                b1 = f.read(1)
                if not b0 or not b1:
                    break
                color = (b1[0] << 8) | b0[0]
                bitmap[x, y] = color
    return bitmap

def connect_to_wifi():
    splash = displayio.Group()
    value_label = label.Label(
        font_30, text="Connecting", color=0x00FF00, anchor_point=(0.5, 0.5), anchored_position=(140, 120)
    )
    splash.append(value_label)
    display.root_group = splash
    

    for _ in range(3):
        try:
            print("Connecting to WiFi...")
            wifi.radio.connect(WIFI_SSID, WIFI_PASSWORD)
            print("Connected:", wifi.radio.ipv4_address)
            value_label.text = f"IP: {wifi.radio.ipv4_address}"
            time.sleep(2)
            return True
        except Exception as e:
            print(f"WiFi connection failed: {e}")
            value_label.text = "WiFi Failed"
            time.sleep(2)
    return False

def start_ap_mode():
    try:
        ap_ssid = "DexcomConfig"
        ap_password = "config123"

        # start the access point
        wifi.radio.enabled = True
        wifi.radio.start_ap(ssid=ap_ssid, password=ap_password)

        ip = wifi.radio.ipv4_address_ap
        print("Access point created with SSID: {}, password: {}".format(ap_ssid, ap_password))
        print(f"My IP address is {ip}")

        splash = displayio.Group()
        splash.append(
            label.Label(
                font_30,
                text=f"AP Mode:\n{ap_ssid}\nIP: {ip}",
                color=0xFFFF00,
                anchor_point=(0.5, 0.5),
                anchored_position=(140, 120),
            )
        )
        display.root_group = splash
        return True
    except Exception as e:
        print(f"Failed to start AP mode: {e}")
        splash = displayio.Group()
        splash.append(
            label.Label(
                font_40,
                text="AP Mode Failed",
                color=0xFF0000,
                anchor_point=(0.5, 0.5),
                anchored_position=(140, 120),
            )
        )
        display.root_group = splash
        return False
    
def screen_off():
    backlight.duty_cycle = 0
    display.root_group = None     
    
    
def get_battery_voltage(pin):
    raw = pin.value
    voltage = (raw / 65535) * 3.3 * 2  # 16-bit ADC, 3.3 V ref, divider ×2
    return voltage

def voltage_to_percent(vbat_pin):
    total = 0
    for _ in range(10):
        raw = vbat_pin.value
        voltage = (raw / 65535) * 3.3 * 2
        perc = 0
        if voltage >= 4.2:
            perc = 100
        elif voltage <= 3.0:
            perc = 0
        else:
            perc = int((voltage - 3.0) / (4.2 - 3.0) * 100)
        total += perc
        time.sleep(0.05)  # Faster sampling
    return round(total / 10)
    

def flash_red(times: int = 8, on_time: float = 0.12, off_time: float = 0.12):
    if display.root_group is None:
        return

    group = display.root_group

    for _ in range(times):
        if not alarm_active:          # allow instant cancel if user touches to silence
            break
        group.append(red_tilegrid)
        time.sleep(on_time)
        group.remove(red_tilegrid)
        time.sleep(off_time)

def play_alarm(current_glucose):
    global alarm_active, touch
    print("ALARM: Low glucose! Touch to silence.")
    alarm_active = True
    
    flash_red(times=20)
        
    
    try:
        # deinit the main touch BEFORE creating alarm touch
        if touch:
            try:
                touch.deinit()
            except:
                pass
        touch = None
        gc.collect()
        time.sleep(0.2)
        
        with open("/audio/basic.wav", "rb") as f:
            wave = WaveFile(f)
            audio.play(wave)
            
            # Now create dedicated alarm silence touch on A3
            touch_silence = None
            try:
                touch_silence = touchio.TouchIn(board.A2)
                time.sleep(0.2)
                touch_silence.threshold = touch_silence.raw_value + 1000
                
                touch_count = 0
                while audio.playing and touch_count < 3:
                    if touch_silence.value:
                        touch_count += 1
                    else:
                        touch_count = 0
                    time.sleep(0.01)
                
            except Exception as e:
                print(f"Alarm touch error: {e}")
                # Continue audio even if touch fails
                while audio.playing:
                    time.sleep(0.1)
            finally:
                if touch_silence:
                    try:
                        touch_silence.deinit()
                    except:
                        pass
                    touch_silence = None
            
            audio.stop()
            gc.collect()
            time.sleep(0.2)
            
    except Exception as e:
        print("Alarm error:", e)
    
    alarm_active = False
    print("Alarm stopped. Back to normal.")
    
    # RE-INITIALIZE normal touch
    time.sleep(0.3)
    init_touch()
    
    
def check_alarm(value, mmol):
    global alarm_active, last_low

    # Force test value if test mode is on
    if FORCE_ALARM_TEST:
        value = 2.0

    low_threshold = 3.9 if mmol else 70
    if value is not None and value < low_threshold and not alarm_active:
        print("LOW GLUCOSE DETECTED -> TRIGGERING ALARM NOW")
        play_alarm(value)
        last_low = value
    
    
# main display
def show_glucose(value, trend, latest_reading_time, previous_glucose=None):
    global last_reading
    gc.collect()
    splash = displayio.Group()
   
    # Normal new-reading detection
    new_reading = False
    if latest_reading_time != last_reading:
        new_reading = True
        last_reading = latest_reading_time

    # FORCE TEST MODE 
    if FORCE_ALARM_TEST:
        new_reading = True
        value = 2.0                   

    if not new_reading:
        return

    

    if value is not None:
        display_value = round(value, 1) if not MMOL else round(value / 18, 1)
    else:
        display_value = None


    if display_value is not None:
        if MMOL:
            if 4.2 <= display_value <= 8:
                color = 0x00FF00  # Green - target
                status = "TARGET"
            elif 8 < display_value <= 12:
                color = 0xFFFF00  # Yellow - elevated
                status = "HIGH"
            elif display_value > 12:
                color = 0xFF5C00  # Orange - very high
                status = "VERY HIGH"
            elif display_value < 3.9:
                color = 0xFF0000  # Red - low
                status = "LOW"
                check_alarm(value, MMOL)
        else:
            # mg/dL 
            if 76 <= display_value <= 144:
                color = 0x00FF00  # Green - target
                status = "TARGET"
            elif 144 < display_value <= 216:
                color = 0xFFFF00  # Yellow - elevated
                status = "HIGH"
            elif display_value > 216:
                color = 0xFF5C00  # Orange - very high
                status = "VERY HIGH"
            elif display_value < 76:
                color = 0xFF0000  # Red - low
                status = "LOW"
                check_alarm(value, MMOL)
    else:
        color = 0xFF0000
        status = "ERROR"

    value_text = str(display_value) if display_value is not None else "No Data"
    
    # unit indicator
    unit = "mmol/L" if MMOL else "mg/dL"
    value_with_unit = f"{value_text}\n{unit}"
    
    value_label = label.Label(
        font_80,
        text=value_text,
        color=color,
        anchor_point=(0.5, 0.5),
        anchored_position=(140, 100)
    )
    splash.append(value_label)

    # unit label
    unit_label = label.Label(
        font_30,
        text=unit,
        color=0xAAAAAA,
        anchor_point=(0.5, 0.5),
        anchored_position=(140, 155)
    )
    splash.append(unit_label)

    # time
    current_time = time.localtime()
    time_text = "{:02}:{:02}".format(current_time.tm_hour, current_time.tm_min)
    time_label = label.Label(
        font_30,
        text=time_text,
        color=0xFFFFFF,
        anchor_point=(0.0, 0.0),
        anchored_position=(10, 10)
    )
    splash.append(time_label)

    # delta
    if value is not None and previous_glucose is not None:
        delta = value - previous_glucose
        if MMOL:
            delta = round(delta / 18, 1)
        delta_text = f"{delta:+.1f}"
        delta_color = 0x00FF00 if delta <= 0 else 0xFFFF00  # Green if dropping, yellow if rising
    else:
        delta_text = "--"
        delta_color = 0xAAAAAA

    delta_label = label.Label(
        font_30,
        text=delta_text,
        color=delta_color,
        anchor_point=(1.0, 0.0),
        anchored_position=(270, 10)
    )
    splash.append(delta_label)

    # trend 
    try:
        arrow_path = TREND_ARROWS[trend]
        bitmap = displayio.OnDiskBitmap(open(arrow_path, "rb"))
        arrow_tile = displayio.TileGrid(
            bitmap,
            pixel_shader=displayio.ColorConverter(input_colorspace=displayio.Colorspace.RGB565)
        )
        arrow_tile.x = 140 - bitmap.width // 2
        arrow_tile.y = 175
        splash.append(arrow_tile)

    except Exception as e:
        print(f"Failed to load arrow: {e}")



    # battery
    percent = voltage_to_percent(vbat_pin)
    
    # Color battery indicator based on level
    if percent >= 50:
        bat_color = 0x00FF00
    elif percent >= 20:
        bat_color = 0xFFFF00
    else:
        bat_color = 0xFF0000

    bat_label = label.Label(
        font_30,
        text=f"🔋 {percent}%",
        color=bat_color,
        anchor_point=(0.0, 1.0),
        anchored_position=(10, 230)
    )
    splash.append(bat_label)

    print("Checking for alarm")
    check_alarm(value, MMOL)
    # Render
    display.root_group = splash
    print(f"Display updated: {display_value} {unit} | Trend: {trend} | Battery: {percent}% | Status: {status}")


# Dexcom API login
def dexcom_login(https_session):
    url = f"https://{DEXCOM_SERVER}/ShareWebServices/Services/General/LoginPublisherAccountByName"
    headers = {"Content-Type": "application/json"}
    payload = f'{{"accountName":"{DEXCOM_USERNAME}","password":"{DEXCOM_PASSWORD}","applicationId":"d89443d2-327c-4a6f-89e5-496bbb0317db"}}'
    try:
        r = https_session.post(url, headers=headers, data=payload)
        if r.status_code == 200:
            return r.text.strip('"')
        print(f"Login failed: Status {r.status_code}")
        return None
    except Exception as e:
        print(f"Login error: {e}")
        return None

def get_glucose(https_session, session_id):
    global last_ssid
    
    url = (
        f"https://{DEXCOM_SERVER}/ShareWebServices/Services/Publisher/ReadPublisherLatestGlucoseValues?sessionID={session_id}&minutes=1440&maxCount=2")
    headers = {"Content-Type": "application/json"}
    
    try:
        r = https_session.post(url, headers=headers, data="{}")
        if r.status_code == 200:
            data = r.json()
            if data and len(data) >= 2:
                latest_value = data[0]["Value"]
                latest_trend = data[0]["Trend"]
                previous_value = data[1]["Value"]
                previous_trend = data[1]["Trend"]
                latest_reading_time = data[0]["WT"]
                
                
                
                return (latest_value, latest_trend), (previous_value, previous_trend), (latest_reading_time)

        print(f"Glucose fetch failed: Status {r.status_code}")
        return None, None
    except Exception as e:
        print(f"Glucose fetch error: {e} -- Possible Invalid User/Pass")
        return None, None

def start_webserver(pool, https_session, ap_mode=False):
    """Start web server with redesigned UI"""
    try:
        server = Server(pool, root_path="/")
    except Exception as e:
        print(f"Failed to initialize server: {e}")
        return None

    # ============================================================
    # INDEX ROUTE - Serve the redesigned settings page
    # ============================================================
    @server.route("/", methods=["GET"])
    def index(request: Request):
        html = f"""
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Dexcom Display Settings</title>
            <style>
                * {{
                    margin: 0;
                    padding: 0;
                    box-sizing: border-box;
                }}

                body {{
                    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                    min-height: 100vh;
                    padding: 20px;
                    display: flex;
                    justify-content: center;
                    align-items: center;
                }}

                .container {{
                    background: white;
                    border-radius: 16px;
                    box-shadow: 0 20px 60px rgba(0, 0, 0, 0.15);
                    max-width: 600px;
                    width: 100%;
                    overflow: hidden;
                }}

                .header {{
                    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                    padding: 40px 30px;
                    text-align: center;
                    color: white;
                }}

                .header h1 {{
                    font-size: 28px;
                    margin-bottom: 8px;
                    font-weight: 600;
                }}

                .header p {{
                    font-size: 14px;
                    opacity: 0.9;
                    font-weight: 400;
                }}

                .content {{
                    padding: 40px 30px;
                }}

                form {{
                    display: flex;
                    flex-direction: column;
                    gap: 28px;
                }}

                .section {{
                    border-bottom: 1px solid #f0f0f0;
                    padding-bottom: 28px;
                }}

                .section:last-child {{
                    border-bottom: none;
                }}

                .section-title {{
                    font-size: 13px;
                    font-weight: 600;
                    color: #667eea;
                    text-transform: uppercase;
                    letter-spacing: 0.5px;
                    margin-bottom: 16px;
                }}

                .form-group {{
                    display: flex;
                    flex-direction: column;
                    gap: 8px;
                    margin-bottom: 16px;
                }}

                .form-group:last-child {{
                    margin-bottom: 0;
                }}

                label {{
                    font-size: 14px;
                    font-weight: 500;
                    color: #333;
                }}

                input[type="text"],
                input[type="password"] {{
                    width: 100%;
                    padding: 12px 14px;
                    font-size: 15px;
                    border: 1.5px solid #e0e0e0;
                    border-radius: 8px;
                    transition: all 0.3s ease;
                    background: #fafafa;
                }}

                input[type="text"]:focus,
                input[type="password"]:focus {{
                    background: white;
                    border-color: #667eea;
                    outline: none;
                    box-shadow: 0 0 0 3px rgba(102, 126, 234, 0.1);
                }}

                .toggle-group {{
                    display: flex;
                    align-items: center;
                    gap: 12px;
                    padding: 16px;
                    background: #f8f9fa;
                    border-radius: 8px;
                }}

                .toggle {{
                    position: relative;
                    width: 50px;
                    height: 28px;
                    flex-shrink: 0;
                }}

                .toggle input {{
                    display: none;
                }}

                .slider {{
                    position: absolute;
                    cursor: pointer;
                    top: 0;
                    left: 0;
                    right: 0;
                    bottom: 0;
                    background-color: #d0d0d0;
                    border-radius: 28px;
                    transition: background-color 0.3s ease;
                }}

                .slider:before {{
                    position: absolute;
                    content: "";
                    height: 24px;
                    width: 24px;
                    left: 2px;
                    bottom: 2px;
                    background-color: white;
                    border-radius: 50%;
                    transition: transform 0.3s ease;
                    box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
                }}

                input:checked + .slider {{
                    background-color: #667eea;
                }}

                input:checked + .slider:before {{
                    transform: translateX(22px);
                }}

                .toggle-label {{
                    font-size: 14px;
                    font-weight: 500;
                    color: #333;
                }}

                .button-group {{
                    display: flex;
                    gap: 12px;
                    margin-top: 8px;
                }}

                input[type="submit"] {{
                    flex: 1;
                    padding: 14px;
                    font-size: 16px;
                    font-weight: 600;
                    border: none;
                    border-radius: 8px;
                    cursor: pointer;
                    transition: all 0.3s ease;
                    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                    color: white;
                }}

                input[type="submit"]:hover {{
                    transform: translateY(-2px);
                    box-shadow: 0 10px 20px rgba(102, 126, 234, 0.3);
                }}

                input[type="submit"]:active {{
                    transform: translateY(0);
                }}

                .status-badge {{
                    display: inline-block;
                    padding: 6px 12px;
                    border-radius: 20px;
                    font-size: 12px;
                    font-weight: 600;
                    margin-top: 12px;
                }}

                .status-connected {{
                    background-color: #d4edda;
                    color: #155724;
                }}

                .status-ap {{
                    background-color: #fff3cd;
                    color: #856404;
                }}

                @media (max-width: 480px) {{
                    .content {{
                        padding: 24px 20px;
                    }}
                    .header {{
                        padding: 30px 20px;
                    }}
                    .header h1 {{
                        font-size: 24px;
                    }}
                    form {{
                        gap: 20px;
                    }}
                }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>Dexcom Display</h1>
                    <p>Configure your glucose monitoring display settings</p>
                    <div class="status-badge {"status-connected" if not ap_mode else "status-ap"}">
                        {"✓ Connected to WiFi" if not ap_mode else "⚙ Configuration Mode"}
                    </div>
                </div>

                <div class="content">
                    <form method="POST" action="/save">
                        <!-- WiFi Section -->
                        <div class="section">
                            <div class="section-title">📡 WiFi Configuration</div>
                            <div class="form-group">
                                <label for="WIFI_SSID">Network Name (SSID)</label>
                                <input type="text" id="WIFI_SSID" name="WIFI_SSID" placeholder="Enter your WiFi network name" value="{WIFI_SSID}" required>
                            </div>
                            <div class="form-group">
                                <label for="WIFI_PASSWORD">Network Password</label>
                                <input type="password" id="WIFI_PASSWORD" name="WIFI_PASSWORD" placeholder="Enter your WiFi password" value="{WIFI_PASSWORD}" required>
                            </div>
                        </div>

                        <!-- Dexcom Section -->
                        <div class="section">
                            <div class="section-title">🩺 Dexcom Account</div>
                            <div class="form-group">
                                <label for="DEXCOM_USERNAME">Username</label>
                                <input type="text" id="DEXCOM_USERNAME" name="DEXCOM_USERNAME" placeholder="Your Dexcom username" value="{DEXCOM_USERNAME}" required>
                            </div>
                            <div class="form-group">
                                <label for="DEXCOM_PASSWORD">Password</label>
                                <input type="password" id="DEXCOM_PASSWORD" name="DEXCOM_PASSWORD" placeholder="Your Dexcom password" value="{DEXCOM_PASSWORD}" required>
                            </div>
                            <div class="form-group">
                                <label for="DEXCOM_SERVER">Server</label>
                                <input type="text" id="DEXCOM_SERVER" name="DEXCOM_SERVER" placeholder="e.g., share2.dexcom.com" value="{DEXCOM_SERVER}" required>
                            </div>
                        </div>

                        <!-- Display Section -->
                        <div class="section">
                            <div class="section-title">🎨 Display Settings</div>
                            <div class="form-group">
                                <label for="DISPLAY_NAME">Display Name</label>
                                <input type="text" id="DISPLAY_NAME" name="DISPLAY_NAME" placeholder="Enter a name for this display" value="{DISPLAY_NAME}">
                            </div>
                            <div class="toggle-group">
                                <label class="toggle">
                                    <input type="checkbox" name="MMOL" {"checked" if MMOL else ""}>
                                    <span class="slider"></span>
                                </label>
                                <span class="toggle-label">Show glucose in mmol/L (instead of mg/dL)</span>
                            </div>
                        </div>

                        <!-- Submit Button -->
                        <div class="button-group">
                            <input type="submit" value="Save Settings">
                        </div>
                    </form>
                </div>
            </div>
        </body>
        </html>
        """
        return Response(request, html, content_type="text/html")

    # ============================================================
    # SAVE ROUTE - Handle form submission
    # ============================================================
    @server.route("/save", methods=["POST"])
    def save(request: Request):
        global settings, session, WIFI_SSID, WIFI_PASSWORD, DEXCOM_USERNAME, DEXCOM_PASSWORD, DEXCOM_SERVER, DISPLAY_NAME, MMOL, last_fetch_time, last_reading

        form_data = request.form_data
        old_ssid = WIFI_SSID

        # Build new settings dict
        new_settings = {
            "WIFI_SSID": url_decode(form_data.get("WIFI_SSID", WIFI_SSID)),
            "WIFI_PASSWORD": url_decode(form_data.get("WIFI_PASSWORD", WIFI_PASSWORD)),
            "DEXCOM_USERNAME": url_decode(form_data.get("DEXCOM_USERNAME", DEXCOM_USERNAME)),
            "DEXCOM_PASSWORD": url_decode(form_data.get("DEXCOM_PASSWORD", DEXCOM_PASSWORD)),
            "DEXCOM_SERVER": url_decode(form_data.get("DEXCOM_SERVER", DEXCOM_SERVER)),
            "DISPLAY_NAME": url_decode(form_data.get("DISPLAY_NAME", DISPLAY_NAME)),
            "MMOL": "MMOL" in form_data
        }

        # Write to file first
        try:
            with open(SETTINGS_FILE, "w") as f:
                json.dump(new_settings, f)
                f.flush()
                os.sync()
            print("Settings written to flash.")
        except Exception as e:
            print("Write failed:", e)
            return Response(
                request,
                "<script>alert('ERROR: Could not write settings.json'); window.location='/';</script>",
                content_type="text/html"
            )

        # Reload from file and update globals
        try:
            with open(SETTINGS_FILE, "r") as f:
                reloaded = json.load(f)
                for k, v in reloaded.items():
                    if isinstance(v, str):
                        reloaded[k] = url_decode(v)
                settings.update(reloaded)
                globals().update(settings)
            print("Settings reloaded and globals updated.")
        except Exception as e:
            print("Reload failed:", e)
            return Response(
                request,
                "<script>alert('ERROR: Could not reload settings'); window.location='/';</script>",
                content_type="text/html"
            )

        # Check if WiFi settings changed
        wifi_changed = (new_settings["WIFI_SSID"] != old_ssid or
                        new_settings["WIFI_PASSWORD"] != WIFI_PASSWORD)

        if wifi_changed:
            try:
                wifi.radio.stop_ap()
                print("AP stopped")
                time.sleep(0.5)
            except Exception as e:
                print("stop_ap error:", e)

            if connect_to_wifi():
                session = dexcom_login(https_session) or session
                msg = "✓ Settings saved! Connected to new WiFi."
            else:
                start_ap_mode()
                msg = "✓ Settings saved, but WiFi failed – back in AP mode."
        else:
            # No WiFi change, just refresh Dexcom session
            session = dexcom_login(https_session) or session
            msg = "✓ Settings saved and applied."

        # ============================================================
        # FORCE IMMEDIATE DISPLAY REFRESH
        # ============================================================
        # Reset fetch timer to force immediate glucose fetch on next loop
        last_fetch_time = 0
        # Reset last_reading to force display update (bypass new_reading check)
        last_reading = None
        
        # Try to fetch and display glucose immediately
        try:
            print("Attempting immediate glucose fetch...")
            points = get_glucose(https, session)
            print(f"Fetch result: {points}")
            if points and len(points) == 3:
                (value, trend), (prev_value, _), latest_reading_time = points
                print(f"Got glucose: {value}, trend: {trend}")
                show_glucose(value, trend, latest_reading_time, prev_value)
                msg += " | Display updated."
            else:
                print("No valid glucose data returned")
                show_glucose(None, None, None)
                msg += " | Failed to fetch glucose data."
        except Exception as e:
            print(f"Immediate refresh error: {e}")
            import traceback
            traceback.print_exc()
            msg += " | Could not update display."

        return Response(
            request,
            f"<script>alert('{msg}'); window.location='/';</script>",
            content_type="text/html"
        )
    # ============================================================
    # START SERVER
    # ============================================================
    try:
        if ap_mode:
            ip_source = wifi.radio.ipv4_address_ap
        else:
            ip_source = wifi.radio.ipv4_address

        deadline = time.monotonic() + 3.0
        while time.monotonic() < deadline:
            ip = ip_source
            if ip and str(ip) != "0.0.0.0":
                break
            time.sleep(0.1)
        else:
            print("Timeout – no valid IP for web server")
            return None

        server.start(host=str(ip), port=80)
        print(f"✓ Web server listening on http://{ip}/ (AP={ap_mode})")
        return server
    except Exception as e:
        print(f"Server start failed: {e}")
        return None



def attempt_sleep():
    """Attempt to enter deep sleep safely."""
    global touch
    
    print("Going to sleep...")
    
    # CRITICAL: Deinit touch BEFORE sleep setup
    if touch:
        try:
            touch.deinit()
        except Exception as e:
            print(f"Touch deinit before sleep: {e}")
        touch = None
    
    gc.collect()
    time.sleep(0.3)  # Give touch hardware time to release
    
    # Turn off screen
    screen_off()
    
    # Save wake reason
    alarm.sleep_memory[0] = 1
    
    try:
        # Create touch alarm
        touch_alarm = alarm.touch.TouchAlarm(pin=board.A2)
        print("Touch alarm created, entering deep sleep...")
        time.sleep(0.1)
        
        # Enter deep sleep
        alarm.light_sleep_until_alarms(touch_alarm)
        
    except Exception as e:
        print(f"Sleep setup failed: {e}")
        print("Falling back to light sleep workaround...")
        
        # Fallback: Use a timer instead
        for _ in range(10):
            time.sleep(0.5)
            if touch and touch.value:
                print("Woken by touch during fallback sleep")
                break
        
        alarm.sleep_memory[0] = 0
    
    finally:
        # Clean up alarm objects
        gc.collect()
        time.sleep(0.3)
        
        microcontroller.reset()



# -------- MAIN LOOP --------
gc.collect()
print(f"Free memory: {gc.mem_free()} bytes")
pool = socketpool.SocketPool(wifi.radio)
https = adafruit_requests.Session(pool, ssl.create_default_context())
web_server = None  # in case both Wi-Fi and AP fail





# Try to connect to Wi-Fi
if not connect_to_wifi():
    # Wi-Fi failed → enter AP mode
    if start_ap_mode():
        time.sleep(0.5)
        web_server = start_webserver(pool, https, ap_mode=True)

        # AP mode loop: serve config + try reconnect
        last_bg = 0
        while True:
            if web_server:
                try:
                    web_server.poll()
                except Exception as e:
                    print("Web poll error:", e)
                    web_server = start_webserver(pool, https, ap_mode=True)

            now = time.monotonic()
            if now - last_bg > 5:
                last_bg = now
                if not wifi.radio.connected and not wifi.radio.ap_active:
                    try:
                        print("Background Wi-Fi reconnect...")
                        if connect_to_wifi():
                            print("Wi-Fi connected – leaving AP mode")
                            break
                    except Exception as e:
                        print("Background fail:", e)
                        start_ap_mode()
            time.sleep(0.2)

        # AFTER BREAK: we are now on Wi-Fi → start client-mode server
        web_server = start_webserver(pool, https, ap_mode=False)

    else:
        # AP also failed → hang (no web server)
        while True:
            time.sleep(60)
else:
    # Wi-Fi connected on boot → start client-mode server
    web_server = start_webserver(pool, https, ap_mode=False)

# Login to Dexcom
session = dexcom_login(https)
if not session:
    splash = displayio.Group()
    splash.append(label.Label(font_40, text="Login Failed", color=0xFF0000,
                              anchor_point=(0.5, 0.5), anchored_position=(140, 120)))
    display.root_group = splash

# Main glucose loop
last_fetch_time = 0


while True:
    gc.collect()
    current_time = time.monotonic()
    
    # Initialize touch if needed
    if touch is None:
        init_touch()
    
    if not alarm_active:
        if touch and touch.value:
            if touch_start_time is None:
                touch_start_time = current_time
                print("Touch Started. Hold for Sleep.")
            elif current_time - touch_start_time >= 5:
                # Use safe sleep function
                attempt_sleep()
                touch_start_time = None
                last_fetch_time = 0  # Force immediate update on wake
        else:
            touch_start_time = None
    
    # Fetch glucose every 10 seconds
    if current_time - last_fetch_time >= 10:
        points = get_glucose(https, session)
        if points and len(points) == 3:
            (value, trend), (prev_value, _), latest_reading_time = points
            show_glucose(value, trend, latest_reading_time, prev_value)
        else:
            session = dexcom_login(https) or session
            show_glucose(None, None, None)
        last_fetch_time = current_time
    
    # Keep web server alive
    if web_server:
        try:
            web_server.poll()
        except Exception as e:
            print(f"Web server error: {e}")
            web_server = start_webserver(pool, https, ap_mode=wifi.radio.ap_active)
    
    time.sleep(0.1)