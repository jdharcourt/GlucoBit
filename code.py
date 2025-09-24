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
from adafruit_display_text import label
import adafruit_st7789
import fourwire
import adafruit_requests
import adafruit_bitmap_font.bitmap_font as bitmap_font
from adafruit_httpserver import Server, Request, Response, MIMETypes
from audiocore import WaveFile




MIMETypes.configure(default_to="text/plain")


alarm_active = False
alarm_suppressed = False
last_low = None
last_reading = None

last_ssid = None

session = None
previous_glucose = None


BCLK = board.D5    
LRCLK = board.D6  
DIN = board.D4    
audio = audiobusio.I2SOut(bit_clock=BCLK, word_select=LRCLK, data=DIN)
touch = touchio.TouchIn(board.D0)

previous_glucose = None
# font
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

# display setup 
displayio.release_displays()
spi = board.SPI()
tft_cs = board.D1
tft_dc = board.D2
tft_rst = board.D3

display_bus = fourwire.FourWire(spi, command=tft_dc, chip_select=tft_cs, reset=tft_rst)
display = adafruit_st7789.ST7789(
    display_bus, width=280, height=240, rotation=90, colstart=0, rowstart=20
)

# Trend arrows location 
TREND_ARROWS = {
    1: "/icons/up.bmp", 2: "/icons/up.bmp", 'Flat': "/icons/level.bmp", 
    4: "/icons/down.bmp", 5: "/icons/down.bmp", 6: "/icons/up-right.bmp", 
    7: "/icons/down-right.bmp"
}


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




def alarm():
    global alarm_active, alarm_suppressed
    print("Playing alarm until touched:")
    try:
        with open("/audio/basic.wav", "rb") as wave_file:
            wave = WaveFile(wave_file)
            touch_count = 0
            while touch_count < 3 and alarm_suppressed == False:  # Require multiple touch readings to confirm
                audio.play(wave)
                alarm_active = True
                while audio.playing:
                    if touch.value:
                        touch_count += 1
                    else:
                        touch_count = 0
                    time.sleep(0.01)  
            if audio.playing:
                audio.stop()
                alarm_active = False
                alarm_suppressed = True
            print("Finished")
            
    except Exception as e:
        print(f"Alarm error: {e}")
    
    
def check_alarm(value, mmol):
    global alarm_active, alarm_suppressed, last_low
    low_threshold = 4.2 if mmol else 76
    if value is not None and value < low_threshold and not alarm_active and not alarm_suppressed:
        if last_low != value:  
            alarm()
            last_low = value
    
    
    
# -------- DISPLAY GLUCOSE --------
def show_glucose(value, trend, latest_reading_time, previous_glucose=None):
    global last_reading

    gc.collect()
    splash = displayio.Group()
    
    new_reading = False
    
    if latest_reading_time == last_reading:
        new_reading = False
    else:
        new_reading = True
        last_reading = latest_reading_time
    
    
    
    if new_reading == True:
        if value is not None:
            display_value = round(value, 1) if not MMOL else round(value / 18, 1)
        else:
            display_value = None

        
        if display_value is not None:
            if MMOL:
                if 4.2 <= display_value <= 8:
                    color = 0x00FF00
                elif 8 < display_value <= 12:
                    color = 0xFFFF00
                elif display_value > 12:
                    color = 0xFF5C00
                elif display_value < 4.2:
                    color = 0xFF0000
                    check_alarm(value, MMOL)

            else:
                # mg/dL 
                if 76 <= display_value <= 144:
                    color = 0x00FF00
                elif 144 < display_value <= 216:
                    color = 0xFFFF00
                elif display_value > 216:
                    color = 0xFF5C00
                elif display_value < 76:
                    color = 0xFF0000
                    check_alarm(value, MMOL)

        else:
            color = 0xFF0000


        
        value_label = label.Label(
            font_80, text=str(display_value) if value is not None else "No Data",
            color=color, anchor_point=(0.5, 0.5), anchored_position=(140, 120)
        )
        splash.append(value_label)

        
        current_time = time.localtime()
        time_text = "{:02}:{:02}".format(current_time.tm_hour, current_time.tm_min)
        time_label = label.Label(
            font_30, text=time_text, color=0xFFFFFF, anchor_point=(0.0, 0.0), anchored_position=(25, 20)
        )
        splash.append(time_label)
        
        print(f"Trend value received: '{trend}'")
        print(f"Valid keys: {list(TREND_ARROWS.keys())}")

        if trend in TREND_ARROWS:
            arrow_path = TREND_ARROWS[trend]
            try:
                bitmap = displayio.OnDiskBitmap(open("/icons/level.bmp", "rb"))
                arrow_tile = displayio.TileGrid(bitmap, pixel_shader=bitmap.pixel_shader)
                arrow_tile.x = 140 - bitmap.width // 2
                arrow_tile.y =180
                splash.append(arrow_tile)
            except Exception as e:
                print(f"failed to load arrow: {e}")
        else:
            arrow_label = label.Label(
                font_40, text="?", color=0xFF0000,
                anchor_point=(0.5, 0), anchored_position=(140, 180)
            )
            splash.append(arrow_label)

        # delta
        if value is not None and previous_glucose is not None:
            delta = value - previous_glucose
            if MMOL:
                delta = round(delta / 18, 1)
            delta_text = f"{delta:+.1f}"
        else:
            delta_text = "--"

        delta_label = label.Label(
            font_30, text=delta_text, color=0xFFFFFF,
            anchor_point=(1.0, 0.0), anchored_position=(240, 20)
        )
        splash.append(delta_label)
        
        #print(f"Trend: {trend}, File: {TREND_ARROWS.get(trend, '/icons/up-right.jpg')}")
        #bitmap = displayio.OnDiskBitmap("/icons/up-right.jpg")
        #arrow_tile = displayio.TileGrid(bitmap, pixel_shader=bitmap.pixel_shader)
        #arrow_tile.x = 140 - bitmap.width // 2  # Center horizontally
        #arrow_tile.y = 180  # Same vertical position
        #splash.append(arrow_tile)

        display.root_group = splash


# dexcom api
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
    try:
        server = Server(pool, root_path="/")
    except Exception as e:
        print(f"Failed to initialize server: {e}")
        return None



    
    
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
                body {{
                    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                    background-color: #f0f2f5;
                    margin: 0;
                    padding: 20px;
                    display: flex;
                    justify-content: center;
                    align-items: center;
                    min-height: 100vh;
                }}
                .container {{
                    background: white;
                    padding: 30px;
                    border-radius: 12px;
                    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
                    max-width: 500px;
                    width: 100%;
                }}
                h1 {{
                    color: #333;
                    text-align: center;
                    margin-bottom: 20px;
                    font-size: 24px;
                }}
                form {{
                    display: flex;
                    flex-direction: column;
                    gap: 15px;
                }}
                label {{
                    color: #555;
                    font-size: 16px;
                    margin-bottom: 5px;
                }}
                input[type="text"],
                input[type="password"] {{
                    padding: 10px;
                    border: 1px solid #ddd;
                    border-radius: 6px;
                    font-size: 16px;
                    width: 100%;
                    box-sizing: border-box;
                    transition: border-color 0.3s;
                }}
                input[type="text"]:focus,
                input[type="password"]:focus {{
                    border-color: #007bff;
                    outline: none;
                }}
                input[type="checkbox"] {{
                    margin-right: 10px;
                }}
                .checkbox-label {{
                    display: flex;
                    align-items: center;
                    color: #555;
                    font-size: 16px;
                }}
                input[type="submit"] {{
                    background-color: #007bff;
                    color: white;
                    padding: 12px;
                    border: none;
                    border-radius: 6px;
                    font-size: 16px;
                    cursor: pointer;
                    transition: background-color 0.3s;
                }}
                input[type="submit"]:hover {{
                    background-color: #0056b3;
                }}
                .toggle {{
                  position: relative;
                  display: inline-block;
                  width: 60px;
                  height: 34px;
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
                  background-color: #333;
                  transition: 0.4s;
                  border-radius: 34px;
                }}
                .slider:before {{
                  position: absolute;
                  content: "";
                  height: 26px;
                  width: 26px;
                  left: 4px;
                  bottom: 4px;
                  background-color: #FFF;
                  transition: 0.4s;
                  border-radius: 50%;
                }}
                input:checked + .slider {{
                  background-color: #060;
                }}
                input:checked + .slider:before {{
                  transform: translateX(26px);
                }}
            </style>
        </head>
        <body>
            <div class="container">
                <h1>Dexcom Display Settings</h1>
                <form method="POST" action="/save">
                    <label for="WIFI_SSID">WiFi SSID</label>
                    <input type="text" id="WIFI_SSID" name="WIFI_SSID" value="{WIFI_SSID}">
                    <label for="WIFI_PASSWORD">WiFi Password</label>
                    <input type="password" id="WIFI_PASSWORD" name="WIFI_PASSWORD" value="{WIFI_PASSWORD}">
                    <label for="DEXCOM_USERNAME">Dexcom Username</label>
                    <input type="text" id="DEXCOM_USERNAME" name="DEXCOM_USERNAME" value="{DEXCOM_USERNAME}">
                    <label for="DEXCOM_PASSWORD">Dexcom Password</label>
                    <input type="password" id="DEXCOM_PASSWORD" name="DEXCOM_PASSWORD" value="{DEXCOM_PASSWORD}">
                    <label for="DEXCOM_SERVER">Dexcom Server</label>
                    <input type="text" id="DEXCOM_SERVER" name="DEXCOM_SERVER" value="{DEXCOM_SERVER}">
                    <label for="DISPLAY_NAME">Display Name</label>
                    <input type="text" id="DISPLAY_NAME" name="DISPLAY_NAME" value="{DISPLAY_NAME}">
                    <label class="toggle">
                        <input type="checkbox" name="MMOL" {"checked" if MMOL else ""}>
                        <span class="slider"></span>
                    </label>
                    <span style="margin-left: 10px;">Use mmol/L</span>
                    <input type="submit" value="Save and Apply">
                </form>
            </div>
        </body>
        </html>
        """
        return Response(request, html, content_type="text/html")

    @server.route("/save", methods=["POST"])
    def save(request: Request):
        global settings, WIFI_SSID, WIFI_PASSWORD, DEXCOM_USERNAME, DEXCOM_PASSWORD, DEXCOM_SERVER, DISPLAY_NAME, MMOL, session
        form_data = request.form_data
        last_ssid = WIFI_SSID
        new_settings = {
            "WIFI_SSID": url_decode(form_data.get("WIFI_SSID", WIFI_SSID)),
            "WIFI_PASSWORD": url_decode(form_data.get("WIFI_PASSWORD", WIFI_PASSWORD)),
            "DEXCOM_USERNAME": url_decode(form_data.get("DEXCOM_USERNAME", DEXCOM_USERNAME)),
            "DEXCOM_PASSWORD": url_decode(form_data.get("DEXCOM_PASSWORD", DEXCOM_PASSWORD)),
            "DEXCOM_SERVER": url_decode(form_data.get("DEXCOM_SERVER", DEXCOM_SERVER)),
            "DISPLAY_NAME": url_decode(form_data.get("DISPLAY_NAME", DISPLAY_NAME)),
            "MMOL": "MMOL" in form_data
        }
        settings.update(new_settings)
        WIFI_SSID = settings["WIFI_SSID"]
        WIFI_PASSWORD = settings["WIFI_PASSWORD"]
        DEXCOM_USERNAME = settings["DEXCOM_USERNAME"]
        DEXCOM_PASSWORD = settings["DEXCOM_PASSWORD"]
        DEXCOM_SERVER = settings["DEXCOM_SERVER"]
        DISPLAY_NAME = settings["DISPLAY_NAME"]
        MMOL = settings["MMOL"]
        
        if WIFI_SSID != last_ssid or WIFI_PASSWORD != settings["WIFI_PASSWORD"]:
            wifi.radio.enabled = False
            time.sleep(0.1)
            wifi.radio.enabled = True
            if not connect_to_wifi():
                start_ap_mode()


        try:
            with open(SETTINGS_FILE, "w") as f:
                json.dump(new_settings, f)
            new_session = dexcom_login(https_session)
            if new_session:
                session = new_session
                print("Updated Dexcom session with new credentials.")
                return Response(request, "Settings saved and applied.", content_type="text/plain")
            else:
                print("Failed to update Dexcom session.")
                return Response(request, "Settings saved but failed to update Dexcom session.", content_type="text/plain")
        except Exception as e:
            print(f"Failed to save settings: {e}")
            return Response(request, "Failed to save settings.", content_type="text/plain")

    try:
        ip = wifi.radio.ipv4_address or wifi.radio.ipv4_address_ap
        server.start(str(ip), port=80)
        print(f"Web server started. Access at http://{ip}/")
        return server
    except Exception as e:
        print(f"Server start failed: {e}")
        return None


# -------- MAIN LOOP --------
gc.collect()
print(f"Free memory: {gc.mem_free()} bytes")

pool = socketpool.SocketPool(wifi.radio)
https = adafruit_requests.Session(pool, ssl.create_default_context())

if not connect_to_wifi():
    if start_ap_mode():
        web_server = start_webserver(pool, https)
        while True:
            if web_server:
                try:
                    web_server.poll()
                except Exception as e:
                    print(f"Web server error: {e}")
                    web_server = start_webserver(pool, https)
            time.sleep(1)
    else:
        while True:
            time.sleep(60)

web_server = start_webserver(pool, https)

session = dexcom_login(https)
if not session:
    splash = displayio.Group()
    splash.append(label.Label(font_40, text="Login Failed", color=0xFF0000, anchor_point=(0.5, 0.5), anchored_position=(140, 120)))
    display.root_group = splash

last_fetch_time = 0


while True:
    gc.collect()
    current_time = time.monotonic()
    if current_time - last_fetch_time >= 10:
        points = get_glucose(https, session)
        if points and len(points) == 3:  # Check if points has exactly 3 elements
            latest, previous, latest_reading_time = points
            value, trend = latest
            prev_value, _ = previous
            show_glucose(value, trend, latest_reading_time, prev_value)
        else:
            # Handle fetch failure by attempting re-login
            session = dexcom_login(https)
            if not session:
                show_glucose(None, None, None, None)  # Pass None for all values
            else:
                points = get_glucose(https, session)
                if points and len(points) == 3:
                    latest, previous, latest_reading_time = points
                    value, trend = latest
                    prev_value, _ = previous
                    show_glucose(value, trend, latest_reading_time, prev_value)
                else:
                    show_glucose(None, None, None, None)  # Pass None for all values

        last_fetch_time = current_time

    if web_server:
        try:
            web_server.poll()
        except Exception as e:
            print(f"Web server error: {e}")
            splash = displayio.Group()
            splash.append(
                label.Label(
                    font_40,
                    text="Server Error",
                    color=0xFF0000,
                    anchor_point=(0.5, 0.5),
                    anchored_position=(140, 120),
                )
            )
            display.root_group = splash
            web_server = start_webserver(pool, https)

    time.sleep(1)
