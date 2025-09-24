import time
import board
import wifi
import socketpool
import ssl
import displayio
import json
import os
import gc
from adafruit_display_text import label
import adafruit_st7789
import fourwire
import adafruit_requests
import adafruit_bitmap_font.bitmap_font as bitmap_font
from terminalio import FONT
from adafruit_httpserver import Server, Request, Response, MIMETypes

# Initialize MIME types
MIMETypes.configure(default_to="text/plain")

# -------- CONFIG FILE --------
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

# Load settings from file if exists
settings = default_settings.copy()
if SETTINGS_FILE in os.listdir():
    try:
        with open(SETTINGS_FILE, "r") as f:
            loaded_settings = json.load(f)
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

# -------- DISPLAY SETUP --------
displayio.release_displays()
spi = board.SPI()
tft_cs = board.D1
tft_dc = board.D2
tft_rst = board.D3

display_bus = fourwire.FourWire(spi, command=tft_dc, chip_select=tft_cs, reset=tft_rst)
display = adafruit_st7789.ST7789(
    display_bus, width=280, height=240, rotation=90, colstart=0, rowstart=20
)

# Load font
try:
    font = bitmap_font.load_font("fonts/nunito-75.bdf")
except Exception as e:
    print(f"Font load failed: {e}")
    font = FONT

# Trend arrow mapping
TREND_ARROWS = {
    1: "^^", 2: "^", 3: ">", 4: "v", 5: "vv", 6: "/^", 7: "\\v", 8: "++", 9: "--"
}

# -------- WIFI --------
def connect_to_wifi():
    splash = displayio.Group()
    value_label = label.Label(
        font, text="Connecting", color=0x00FF00, anchor_point=(0.5, 0.5), anchored_position=(140, 120)
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

# -------- ACCESS POINT MODE --------
def start_ap_mode():
    try:
        wifi.radio.start_ap(ssid="DexcomConfig", password="config123")
        ip = wifi.radio.ipv4_address_ap  # <-- correct property for AP mode
        print(f"AP mode started. Connect to DexcomConfig and access http://{ip}/")

        splash = displayio.Group()
        splash.append(label.Label(
            font, text=f"AP Mode: DexcomConfig\nIP: {ip}",
            color=0xFFFF00, anchor_point=(0.5, 0.5), anchored_position=(140, 120)
        ))
        display.root_group = splash
        return True
    except Exception as e:
        print(f"Failed to start AP mode: {e}")
        splash = displayio.Group()
        splash.append(label.Label(
            font, text="AP Mode Failed", color=0xFF0000,
            anchor_point=(0.5, 0.5), anchored_position=(140, 120)
        ))
        display.root_group = splash
        return False


# -------- DISPLAY GLUCOSE --------
def show_glucose(value, trend):
    gc.collect()  # Free memory before updating display
    splash = displayio.Group()
    display_value = round(value / 18, 1) if MMOL and value is not None else value
    value_label = label.Label(
        font, text=str(display_value) if value is not None else "No Data",
        color=0x00FF00 if value is not None else 0xFF0000,
        anchor_point=(0.5, 0.5), anchored_position=(140, 120)
    )
    splash.append(value_label)
    arrow_text = TREND_ARROWS.get(trend, "?") if trend is not None else "?"
    arrow_label = label.Label(
        font, text=arrow_text, color=0x00FF00, anchor_point=(0.5, 0), anchored_position=(140, 180)
    )
    splash.append(arrow_label)
    display.root_group = splash

# -------- DEXCOM API --------
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
    url = f"https://{DEXCOM_SERVER}/ShareWebServices/Services/Publisher/ReadPublisherLatestGlucoseValues?sessionID={session_id}&minutes=1440&maxCount=1"
    headers = {"Content-Type": "application/json"}
    try:
        r = https_session.post(url, headers=headers, data="{}")
        if r.status_code == 200:
            data = r.json()
            if data:
                return data[0]["Value"], data[0]["Trend"]
        print(f"Glucose fetch failed: Status {r.status_code}")
        return None, None
    except Exception as e:
        print(f"Glucose fetch error: {e}")
        return None, None

# -------- WEBSERVER SETUP --------
def start_webserver(pool):
    try:
        server = Server(pool, root_path="/")  # Removed port from constructor
    except Exception as e:
        print(f"Failed to initialize server: {e}")
        return None

    @server.route("/", methods=["GET"])
    def index(request: Request):
        html = f"""
        <html>
            <body>
                <h1>Dexcom Display Settings</h1>
                <form method="POST" action="/save">
                    <label>WiFi SSID: <input name="WIFI_SSID" value="{WIFI_SSID}"></label><br>
                    <label>WiFi Password: <input name="WIFI_PASSWORD" value="{WIFI_PASSWORD}"></label><br>
                    <label>Dexcom Username: <input name="DEXCOM_USERNAME" value="{DEXCOM_USERNAME}"></label><br>
                    <label>Dexcom Password: <input name="DEXCOM_PASSWORD" value="{DEXCOM_PASSWORD}"></label><br>
                    <label>Dexcom Server: <input name="DEXCOM_SERVER" value="{DEXCOM_SERVER}"></label><br>
                    <label>Display Name: <input name="DISPLAY_NAME" value="{DISPLAY_NAME}"></label><br>
                    <label>Use mmol/L: <input type="checkbox" name="MMOL" {"checked" if MMOL else ""}></label><br>
                    <input type="submit" value="Save and Restart">
                </form>
            </body>
        </html>
        """
        return Response(request, html, content_type="text/html")

    @server.route("/save", methods=["POST"])
    def save(request: Request):
        global settings, WIFI_SSID, WIFI_PASSWORD, DEXCOM_USERNAME, DEXCOM_PASSWORD, DEXCOM_SERVER, DISPLAY_NAME, MMOL
        form_data = request.form_data
        new_settings = {
            "WIFI_SSID": form_data.get("WIFI_SSID", WIFI_SSID),
            "WIFI_PASSWORD": form_data.get("WIFI_PASSWORD", WIFI_PASSWORD),
            "DEXCOM_USERNAME": form_data.get("DEXCOM_USERNAME", DEXCOM_USERNAME),
            "DEXCOM_PASSWORD": form_data.get("DEXCOM_PASSWORD", DEXCOM_PASSWORD),
            "DEXCOM_SERVER": form_data.get("DEXCOM_SERVER", DEXCOM_SERVER),
            "DISPLAY_NAME": form_data.get("DISPLAY_NAME", DISPLAY_NAME),
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
        try:
            with open(SETTINGS_FILE, "w") as f:
                json.dump(new_settings, f)
            return Response(request, "Settings saved. Restart device manually.", content_type="text/plain")
        except Exception as e:
            print(f"Failed to save settings: {e}")
            return Response(request, "Failed to save settings.", content_type="text/plain")

    try:
        server.start(str(wifi.radio.ipv4_address), port=80)  # Moved port to start method
        print(f"Web server started. Access at http://{wifi.radio.ipv4_address}/")
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
        web_server = start_webserver(pool)
        while True:
            if web_server:
                try:
                    web_server.poll()
                except Exception as e:
                    print(f"Web server error: {e}")
                    web_server = start_webserver(pool)  # Attempt to restart
            time.sleep(1)
    else:
        while True:
            time.sleep(60)  # Stuck, retry later or handle manually

web_server = start_webserver(pool)
session = dexcom_login(https)
if not session:
    splash = displayio.Group()
    splash.append(label.Label(font, text="Login Failed", color=0xFF0000, anchor_point=(0.5, 0.5), anchored_position=(140, 120)))
    display.root_group = splash

last_fetch_time = 0
while True:
    gc.collect()  # Free memory periodically
    current_time = time.monotonic()
    if current_time - last_fetch_time >= 60:
        value, trend = get_glucose(https, session)
        if value is None:
            session = dexcom_login(https)
            if not session:
                show_glucose(None, None)
                last_fetch_time = current_time
            else:
                value, trend = get_glucose(https, session)
        show_glucose(value, trend)
        last_fetch_time = current_time

    if web_server:
        try:
            web_server.poll()
        except Exception as e:
            print(f"Web server error: {e}")
            splash = displayio.Group()
            splash.append(label.Label(font, text="Server Error", color=0xFF0000, anchor_point=(0.5, 0.5), anchored_position=(140, 120)))
            display.root_group = splash
            web_server = start_webserver(pool)  # Attempt to restart
    time.sleep(1)

