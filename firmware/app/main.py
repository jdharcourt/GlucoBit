


import time
import audiobusio
import audiomixer
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
import terminalio
from adafruit_display_text import label
import adafruit_st7789
import fourwire
import adafruit_requests
import adafruit_bitmap_font.bitmap_font as bitmap_font
from adafruit_httpserver import Server, Request, Response, MIMETypes
from adafruit_display_shapes.roundrect import RoundRect
import analogio
import pwmio
import busio
import microcontroller
import adafruit_ntp
import neopixel
import array
import math
import audiocore

import adafruit_imageload
import rtc
from ota import check_and_update



    
# Check if woken from sleep
if alarm.sleep_memory[0] == 1:
    print("Woke from deep sleep (touch)")
    alarm.sleep_memory[0] = 0
    
    # Reset touch on wake
    try:
        import touchio
        # Deinit touch
        touchio.TouchIn(board.A2).deinit()
    except:
        pass
    
    gc.collect()
    time.sleep(0.5)  



MIMETypes.configure(default_to="text/plain")


alarm_active = False
alarm_suppressed = False
last_low = None
last_reading = None
last_triggered_value = None
last_glucose_cache = None  # (value, trend, latest_reading_time, prev_value)

LOW = 2
HIGH = 17

last_ssid = None

session = None
web_server = None
previous_glucose = None
pending_wifi_reconnect = False
pending_session_refresh = False
pending_display_refresh = False

main_group: displayio.Group | None = None
time_label: label.Label | None = None

# BLE companion-app link (initialised after network setup)
ble_link = None
ble_pushed = None  # (value_mgdl, trend_str, epoch_ts, prev_value) from the app
last_reading_epoch = None  # epoch seconds of the newest displayed reading
last_reading_monotonic = None  # time.monotonic() when it was displayed

FORCE_ALARM_TEST = False
LED_TEST = False

# OTA check interval in seconds; keep this conservative to avoid network churn.
version_check = 3600



BCLK = board.D5    
LRCLK = board.D6  
DIN = board.D4    
audio = audiobusio.I2SOut(bit_clock=BCLK, word_select=LRCLK, data=DIN)


mixer = audiomixer.Mixer(
    voice_count=1,
    sample_rate=44100,
    channel_count=1,
    bits_per_sample=16,
    samples_signed=True
)
pixel_pin = board.A3
num_pixels = 2

COLOR_STOPS = [
    (3.0,  (255, 50, 0)),    # bright red-orange
    (4.0,  (255, 180, 0)),   # strong yellow
    (5.0,  (0, 180, 0)),     # vivid green
    (7.0,  (0, 100, 255)),   # deep blue
    (10.0, (120, 0, 255)),   # rich purple
    (13.0, (80, 0, 120)),    # dark indigo
    (15.0, (200, 0, 150))    # bold magenta
]




pixels = neopixel.NeoPixel(pixel_pin, num_pixels, brightness=0.3, auto_write=False)

def lerp(a, b, t):
    return a + (b-a) * t

def lerp_color(c1, c2, t):
    return (
        int(lerp(c1[0], c2[0], t)),
        int(lerp(c1[1], c2[1], t)),
        int(lerp(c1[2], c2[2], t)),
        
    )

def glucose_to_rgb(glucose):
    # Clamp 
    if glucose <= COLOR_STOPS[0][0]:
        return COLOR_STOPS[0][1]
    if glucose >= COLOR_STOPS[-1][0]:
        return COLOR_STOPS[-1][1]

    # Find the two surrounding stops
    for i in range(len(COLOR_STOPS) - 1):
        g1, c1 = COLOR_STOPS[i]
        g2, c2 = COLOR_STOPS[i + 1]

        if g1 <= glucose <= g2:
            t = (glucose - g1) / (g2 - g1)
            r = int(lerp(c1[0], c2[0], t))
            g = int(lerp(c1[1], c2[1], t))
            b = int(lerp(c1[2], c2[2], t))
            return (r, g, b)




touch_start_time = None
previous_glucose = None

touch = None              
touch_mode = "sleep"

#initialise touch sensor to detect "Sleep"
def init_sleep_touch():
    global touch, touch_mode
    cleanup_touch()                            
    for _ in range(8):
        try:
            touch = touchio.TouchIn(board.A2)
            time.sleep(0.15)
            touch.threshold = touch.raw_value + 1200
            touch_mode = "sleep"
            print("Sleep touch initialized")
            return True
        except Exception as e:
            print("Sleep touch init failed:", e)
            cleanup_touch()
            time.sleep(0.1)
    print("Failed to init sleep touch")
    return False


#Initialise Touch Sensor when alarm is playing
def init_alarm_touch():
    global touch, touch_mode
    cleanup_touch() 
    for _ in range(8):
        try:
            touch = touchio.TouchIn(board.A2)
            time.sleep(0.08)
            touch.threshold = touch.raw_value + 400
            touch_mode = "alarm"
            print("ALARM TOUCH INITIALIZED – instant response")
            return True
        except Exception as e:
            print("Alarm touch init failed:", e)
            cleanup_touch()
            time.sleep(0.08)
    print("Failed to init alarm touch")
    return False



def cleanup_touch():
    global touch
    if touch is not None:
        try:
            touch.deinit()
        except:
            pass
        touch = None
    gc.collect()



def init_hardware():
    global display, display_bus, touch, backlight

    # Re-initialise display
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
    init_sleep_touch()
    



    


# fonts
try:
    font_40 = bitmap_font.load_font("fonts/Nunito-Medium-40.bdf")
    font_30 = bitmap_font.load_font("fonts/Nunito-Medium-30.bdf")
    font_80 = bitmap_font.load_font("fonts/Nunito-Medium-80.bdf")
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
    "MMOL": True,
    "UI_THEME": 1,
    "BACKGROUND_COLOR": "#070B18",
    "ALERT_LOW_MGDL": 70,
    "ALERT_HIGH_MGDL": 180
}


        
# URL decoding 
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


def normalize_alert_thresholds(config):
    try:
        low = int(config.get("ALERT_LOW_MGDL", 70))
    except Exception:
        low = 70
    try:
        high = int(config.get("ALERT_HIGH_MGDL", 180))
    except Exception:
        high = 180
    low = max(55, min(low, 120))
    high = max(120, min(high, 300))
    if low >= high:
        low = 70
        high = 180
    config["ALERT_LOW_MGDL"] = low
    config["ALERT_HIGH_MGDL"] = high


boot_msg = label.Label(
    terminalio.FONT,
    text="Booting...",
    color=0x00FF00,
    anchor_point=(0.5, 0.5),
    anchored_position=(140, 120)
)


# Load settings from file
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
normalize_alert_thresholds(settings)

# Extract settings to variables
WIFI_SSID = settings["WIFI_SSID"]
WIFI_PASSWORD = settings["WIFI_PASSWORD"]
DEXCOM_USERNAME = settings["DEXCOM_USERNAME"]
DEXCOM_PASSWORD = settings["DEXCOM_PASSWORD"]
DEXCOM_SERVER = settings["DEXCOM_SERVER"]
DISPLAY_NAME = settings["DISPLAY_NAME"]
MMOL = settings["MMOL"]
BACKGROUND_COLOR = settings.get("BACKGROUND_COLOR", "#070B18")
ALERT_LOW_MGDL = settings["ALERT_LOW_MGDL"]
ALERT_HIGH_MGDL = settings["ALERT_HIGH_MGDL"]
try:
    UI_THEME = int(settings.get("UI_THEME", 1))
except Exception:
    UI_THEME = 1
if UI_THEME not in (1, 2, 3):
    UI_THEME = 1


def is_setup_needed():
    return (
        DISPLAY_NAME == "DexcomFollowerName"
        or not DEXCOM_USERNAME
        or settings.get("SETUP_MODE", False)
    )


def apply_new_settings(updates):
    """Merge decoded settings into the current config, persist to flash and
    queue deferred application via the pending flags. Shared by the web
    /save handler and the BLE settings characteristic.

    Returns (ok, wifi_changed)."""
    global settings, UI_THEME
    global pending_wifi_reconnect, pending_session_refresh, pending_display_refresh

    old_ssid = settings.get("WIFI_SSID")
    old_password = settings.get("WIFI_PASSWORD")

    settings.update(updates)
    normalize_alert_thresholds(settings)

    try:
        theme_value = int(settings.get("UI_THEME", 1))
    except Exception:
        theme_value = 1
    if theme_value not in (1, 2, 3):
        theme_value = 1
    settings["UI_THEME"] = theme_value

    try:
        with open(SETTINGS_FILE, "w") as f:
            json.dump(settings, f)
            f.flush()
            os.sync()
        print("Settings written to flash.")
    except Exception as e:
        print("Settings write failed:", e)
        return False, False

    globals().update(settings)

    wifi_changed = (settings.get("WIFI_SSID") != old_ssid or
                    settings.get("WIFI_PASSWORD") != old_password)
    pending_wifi_reconnect = wifi_changed
    pending_session_refresh = True
    pending_display_refresh = True
    return True, wifi_changed


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
red_palette[0] = 0xFF0000
red_tilegrid = displayio.TileGrid(red_overlay, pixel_shader=red_palette)





    
# Trend arrows file location 
TREND_ARROWS = {
    'DoubleUp': "/icons/up.bmp", 'FortyFiveUp': "/icons/up-right.bmp", 'SingleUp': "/icons/up.bmp", 'Flat': "/icons/level.bmp", 
    "FortyFiveDown": "/icons/down-right.bmp", 'SingleDown': "/icons/down.bmp", 'DoubleDown': "/icons/down.bmp", 'NonComputable' : "/icons/alert.bmp"
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
        terminalio.FONT, text="Connecting", color=0x00FF00, anchor_point=(0.5, 0.5), anchored_position=(140, 120)
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

    
def get_version():
    try:
        with open("/app/version.txt") as f:
            return f.read().strip()
    except:
        return "0.0.0"


def wt_to_epoch(wt):
    """Dexcom WT timestamp '/Date(1718106000000)/' (ms) -> epoch seconds."""
    try:
        start = wt.index("(") + 1
        digits = ""
        for ch in wt[start:]:
            if ch.isdigit():
                digits += ch
            else:
                break
        return int(digits) // 1000
    except Exception:
        return None



def start_ap_mode():
    try:
        ap_ssid = "DexcomConfig"
        ap_password = "config123"

        # start AP
        wifi.radio.enabled = True
        wifi.radio.start_ap(ssid=ap_ssid, password=ap_password)

        ip = wifi.radio.ipv4_address_ap
        print("Access point created with SSID: {}, password: {}".format(ap_ssid, ap_password))
        print(f"My IP address is {ip}")

        splash = displayio.Group()
        splash.append(
            label.Label(
                terminalio.FONT,
                text=f"Setup Required\n\nUse the GlucoBit app\n(via Bluetooth)\n\nOr connect to WiFi:\n   {ap_ssid}\n   Pass: {ap_password}\nthen open http://{ip}/",
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
                terminalio.FONT,
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
        time.sleep(0.05)  
    return round(total / 10)
    

def flash_red(times: int = 8, on_time: float = 0.12, off_time: float = 0.12):
    if display.root_group is None:
        return

    group = display.root_group

    for _ in range(times):
        if not alarm_active:          # cancel if sensor is touched
            break
        group.append(red_tilegrid)
        time.sleep(on_time)
        group.remove(red_tilegrid)
        time.sleep(off_time)


def play_alarm(current_glucose):
    global alarm_active, last_triggered_value
    if alarm_active:
        return
    print("=== GLUCOSE ALARM ===")
    alarm_active = True
    # Tell the companion app the alarm is sounding (the blocking loop below
    # prevents the main loop's throttled status notify from running).
    if ble_link:
        try:
            ble_link.notify_status(force=True)
        except Exception:
            pass
    init_alarm_touch()


    audio.play(mixer)
    mixer.voice[0].level = 0.5  # 50% volume

    try:
        with open("/audio/basic.wav", "rb") as f:
            wav = audiocore.WaveFile(f)
            mixer.voice[0].play(wav)
            flash_count = 0

            while alarm_active:
                if touch and touch.value:
                    print("ALARM SILENCED BY TOUCH")
                    alarm_active = False
                    break

                # Loop audio when it finishes
                if not mixer.voice[0].playing:
                    mixer.voice[0].play(wav)

                # Flash red
                if display.root_group:
                    display.root_group.append(red_tilegrid)
                time.sleep(0.15)
                if display.root_group:
                    display.root_group.remove(red_tilegrid)
                time.sleep(0.15)
                flash_count += 1

    except Exception as e:
        print("Alarm playback error:", e)
    finally:  # Stop Alarm + Flashing
        audio.stop()
        if display.root_group and red_tilegrid in display.root_group:
            display.root_group.remove(red_tilegrid)
        cleanup_touch()
        init_sleep_touch()
        alarm_active = False


def check_alarm(value, mmol):
    global alarm_active, last_triggered_value

    if value is None:
        return

    if ALERT_LOW_MGDL <= value <= ALERT_HIGH_MGDL:
        last_triggered_value = None
        return

    alarm_kind = "LOW" if value < ALERT_LOW_MGDL else "HIGH"
    check_value = round(value / 18.0, 1) if mmol else int(round(value))

    if not alarm_active and alarm_kind != last_triggered_value:
        print(f"NEW {alarm_kind} READING {check_value} — STARTING PERSISTENT ALARM")
        last_triggered_value = alarm_kind
        play_alarm(check_value)
    
    
def rgb_to_hex(rgb_tuple):       #convert RGB value to HEX to display on-screen
    r, g, b = rgb_tuple
    return (r << 16) | (g << 8) | b


def add_solid_rect(group, x, y, width, height, color):
    """Draw a filled rectangle with displayio."""
    bitmap = displayio.Bitmap(width, height, 1)
    palette = displayio.Palette(1)
    palette[0] = color
    group.append(displayio.TileGrid(bitmap, pixel_shader=palette, x=x, y=y))

def draw_trend_arrow(group, trend, center_x, center_y):
    try:
        arrow_path = TREND_ARROWS.get(trend)
        if arrow_path:
            arrow_bitmap, arrow_palette = adafruit_imageload.load(
                arrow_path,
                bitmap=displayio.Bitmap,
                palette=displayio.Palette
            )
            arrow_tile = displayio.TileGrid(arrow_bitmap, pixel_shader=arrow_palette)
            arrow_tile.x = center_x - arrow_bitmap.width // 2
            arrow_tile.y = center_y - arrow_bitmap.height // 2
            group.append(arrow_tile)
    except Exception as e:
        print(f"Failed to load trend arrow: {e}")
        
def lighten_hex(hex_str, factor=0.3):
    """
    Lighten hex color by blending toward white.
    factor: 0.0 = original, 1.0 = white
    Returns: string like '#rrggbb'
    """
    hex_str = hex_str.lstrip('#')
    if len(hex_str) == 3:
        hex_str = ''.join(c * 2 for c in hex_str)

    r = int(hex_str[0:2], 16)
    g = int(hex_str[2:4], 16)
    b = int(hex_str[4:6], 16)

    r = int(r + (255 - r) * factor)
    g = int(g + (255 - g) * factor)
    b = int(b + (255 - b) * factor)

    return f'#{r:02x}{g:02x}{b:02x}'


def hex_to_color_int(hex_str, default=0x070B18):
    """Convert #RGB/#RRGGBB (or without #) into 0xRRGGBB int."""
    if not isinstance(hex_str, str):
        return default
    value = hex_str.strip().lstrip("#")
    if len(value) == 3:
        value = "".join(ch * 2 for ch in value)
    if len(value) != 6:
        return default
    try:
        return int(value, 16)
    except Exception:
        return default


def build_glucose_view_model(value, trend, previous_glucose):
    if value is not None:
        display_value = round(value / 18, 1) if MMOL else int(round(value))
    else:
        display_value = None

    if value is not None:
        very_high_mgdl = max(250, ALERT_HIGH_MGDL + 70)
        if value < ALERT_LOW_MGDL:
            status = "LOW"
        elif value > very_high_mgdl:
            status = "VERY HIGH"
        elif value > ALERT_HIGH_MGDL:
            status = "HIGH"
        else:
            status = "IN RANGE"
    else:
        status = "NO DATA"

    value_mmol = value / 18.0 if value is not None else 6.0
    rgb_value = glucose_to_rgb(value_mmol) if not LED_TEST else glucose_to_rgb(6.0)
    accent_color = rgb_to_hex(rgb_value)
    bg_color_hex = BACKGROUND_COLOR
    try:
        light_bg_hex = lighten_hex(bg_color_hex)
    except Exception:
        bg_color_hex = "#070B18"
        light_bg_hex = lighten_hex(bg_color_hex)
    bg_color = hex_to_color_int(bg_color_hex, default=0x070B18)
    light_bg = hex_to_color_int(light_bg_hex, default=0x070B18)

    if value is not None and previous_glucose is not None:
        delta = value - previous_glucose
        if MMOL:
            delta = round(delta / 18, 1)
            delta_text = f"{delta:+.1f}"
        else:
            delta_text = f"{int(round(delta)):+d}"
        delta_color = 0x4DFF88 if delta < 0 else (0xFFD34D if delta > 0 else 0xB9C9EA)
    else:
        delta_text = "--"
        delta_color = 0x9AA7C2

    status_color = {
        "LOW": 0xFF4D67,
        "IN RANGE": 0x4DFF88,
        "HIGH": 0xFFD34D,
        "VERY HIGH": 0xFF8C42,
        "NO DATA": 0x9AA7C2,
    }.get(status, 0x9AA7C2)

    trend_text = trend if trend else "Unknown"
    trend_glyph = {
        "DoubleUp": "UPUP",
        "SingleUp": "UP",
        "FortyFiveUp": "UP/",
        "Flat": "FLAT",
        "FortyFiveDown": "DN/",
        "SingleDown": "DN",
        "DoubleDown": "DNDN",
        "NonComputable": "ALERT",
    }.get(trend, "UNK")

    name_text = DISPLAY_NAME.strip() if DISPLAY_NAME else "Dexcom"
    if len(name_text) > 18:
        name_text = name_text[:17] + "."

    return {
        "display_value": display_value,
        "value_text": str(display_value) if display_value is not None else "--",
        "unit": "mmol/L" if MMOL else "mg/dL",
        "status": status,
        "status_color": status_color,
        "delta_text": delta_text,
        "delta_color": delta_color,
        "trend_text": trend_text[:14],
        "trend_glyph": trend_glyph,
        "trend_key": trend,
        "name_text": name_text,
        "rgb_value": rgb_value,
        "accent_color": accent_color,
        "bg_color_hex": bg_color_hex,
        "bg_color": bg_color,
        "light_bg": light_bg,
    }
def draw_border(group, x , y, w, h , radius, color, outline, thick):
    radius = max(0, min(radius, w // 2, h // 2))
    rect = RoundRect(x = x, y= y , width = w, height = h, r = radius, fill=color,
                           outline= outline,
                           stroke=thick
                )
    group.append(rect)
    
def draw_round_rect(group, x , y, w, h , radius, color):
    radius = max(0, min(radius, w // 2, h // 2))
    rect = RoundRect(x = x, y= y , width = w, height = h, r = radius, fill=color
    )
    group.append(rect)




    

def render_ui_theme_1(group, model):
    global time_label
    draw_round_rect(group, 0, 0, 280, 240, 15, model["light_bg"])
    add_solid_rect(group, 0, 0, 280, 34, model["bg_color"])
    draw_round_rect(group, 0, 34, 280, 4, 15, model["accent_color"])
    draw_round_rect(group, 8, 46, 264, 122, 15, model["bg_color"])
    draw_round_rect(group, 8, 176, 126, 56, 15, model["bg_color"])
    draw_round_rect(group, 146, 176, 126, 56, 15, model["bg_color"])

    group.append(label.Label(terminalio.FONT, text=model["name_text"], color=0xDDE7FF, anchor_point=(0.0, 0.0), anchored_position=(10, 9)))
    time_label = label.Label(terminalio.FONT, text="--:--:--", color=0xEAF1FF, anchor_point=(1.0, 0.0), anchored_position=(270, 9))
    group.append(time_label)

    group.append(label.Label(terminalio.FONT, text=model["status"], color=model["status_color"], anchor_point=(0.5, 0.0), anchored_position=(140, 56)))
    group.append(label.Label(font_80, text=model["value_text"], color=model["accent_color"], anchor_point=(0.5, 0.5), anchored_position=(140, 106)))
    group.append(label.Label(terminalio.FONT, text=model["unit"], color=0xAFC1E8, anchor_point=(0.5, 0.0), anchored_position=(140, 146)))
    group.append(label.Label(terminalio.FONT, text="TREND", color=0xAFC1E8, anchor_point=(0.0, 0.0), anchored_position=(16, 184)))
    group.append(label.Label(terminalio.FONT, text=model["trend_text"], color=0xDDE7FF, anchor_point=(0.5, 1.0), anchored_position=(71, 228)))
    group.append(label.Label(terminalio.FONT, text="DELTA", color=0xAFC1E8, anchor_point=(0.0, 0.0), anchored_position=(154, 184)))
    group.append(label.Label(font_40, text=model["delta_text"], color=model["delta_color"], anchor_point=(0.5, 0.5), anchored_position=(209, 209)))
    draw_trend_arrow(group, model["trend_key"], 71, 204)


def render_ui_theme_2(group, model):
    global time_label
    bg_group = displayio.Group()
    fg_group = displayio.Group()
    group.append(bg_group)
    group.append(fg_group)

    add_solid_rect(bg_group, 0, 0, 280, 240, model["light_bg"])
    draw_round_rect(bg_group, 0, 0, 280, 50, 15, model["accent_color"])
    draw_round_rect(bg_group, 15, 60, 250, 120, 15, model["bg_color"])
    draw_round_rect(bg_group, 0, 190, 280, 60, 15, model["bg_color"])
    draw_round_rect(bg_group, 138, 190, 4, 50, 15, model["accent_color"])

    fg_group.append(label.Label(terminalio.FONT, text=model["name_text"], color=0x101418, anchor_point=(0.0, 0.0), anchored_position=(10, 14)))
    time_label = label.Label(terminalio.FONT, text="--:--:--", color=0x101418, anchor_point=(1.0, 0.0), anchored_position=(270, 14))
    fg_group.append(time_label)
    fg_group.append(label.Label(terminalio.FONT, text=model["status"], color=0x101418, anchor_point=(0.5, 0.0), anchored_position=(140, 32)))

    fg_group.append(label.Label(font_80, text=model["value_text"], color=model["accent_color"], anchor_point=(0.5, 0.5), anchored_position=(140, 110)))
    fg_group.append(label.Label(font_30, text=model["unit"], color=0xB9C9EA, anchor_point=(0.5, 0.0), anchored_position=(140, 150)))

    fg_group.append(label.Label(terminalio.FONT, text="TREND", color=0x8FA2C9, anchor_point=(0.0, 0.0), anchored_position=(14, 198)))
    fg_group.append(label.Label(terminalio.FONT, text=model["trend_glyph"], color=0xDDE7FF, anchor_point=(0.0, 0.0), anchored_position=(14, 216)))
    draw_trend_arrow(fg_group, model["trend_key"], 106, 216)

    fg_group.append(label.Label(terminalio.FONT, text="DELTA", color=0x8FA2C9, anchor_point=(0.0, 0.0), anchored_position=(154, 198)))
    fg_group.append(label.Label(font_30, text=model["delta_text"], color=model["delta_color"], anchor_point=(0.0, 0.0), anchored_position=(154, 212)))


def render_ui_theme_3(group, model):
    global time_label
    draw_border(group, 0, 0, 280, 240, 50, model["bg_color"], model["accent_color"], 8)

    time_label = label.Label(terminalio.FONT, text="--:--:--", color=0xC6CAD4, anchor_point=(0.0, 0.0), anchored_position=(30, 16))
    group.append(time_label)
    group.append(label.Label(terminalio.FONT, text=model["name_text"], color=0x9EA4B5, anchor_point=(1.0, 0.0), anchored_position=(2, 16)))
    group.append(label.Label(terminalio.FONT, text=model["status"], color=model["status_color"], anchor_point=(0.5, 0.0), anchored_position=(140, 44)))

    group.append(label.Label(font_80, text=model["value_text"], color=0xF3F5FA, anchor_point=(0.5, 0.5), anchored_position=(140, 110)))
    group.append(label.Label(terminalio.FONT, text=model["unit"], color=0xA4AABC, anchor_point=(0.5, 0.0), anchored_position=(140, 148)))

    group.append(label.Label(font_30, text=model["delta_text"], color=model["delta_color"], anchor_point=(0.0, 1.0), anchored_position=(25, 224)))
    draw_trend_arrow(group, model["trend_key"], 140, 190)


def show_glucose(value, trend, latest_reading_time, previous_glucose=None):
    global last_reading, main_group

    gc.collect()
    main_group = displayio.Group()
    display.root_group = main_group

    new_reading = False
    if latest_reading_time != last_reading:
        new_reading = True
        last_reading = latest_reading_time

    if FORCE_ALARM_TEST:
        new_reading = True
        value = 2.0

    model = build_glucose_view_model(value, trend, previous_glucose)
    pixels[0] = model["rgb_value"]
    pixels[1] = model["rgb_value"]
    pixels.show()

    try:
        current_theme = int(UI_THEME)
    except Exception:
        current_theme = 1
    if current_theme not in (1, 2, 3):
        current_theme = 1

    if current_theme == 2:
        render_ui_theme_2(main_group, model)
    elif current_theme == 3:
        render_ui_theme_3(main_group, model)
    else:
        render_ui_theme_1(main_group, model)

    print(f"Display updated: {model['display_value']} {model['unit']} | Trend: {trend} | Status: {model['status']} | UI: {current_theme}")

    if new_reading and value is not None:
        print("Checking for alarm")
        check_alarm(value, MMOL)


def show_setup_screen(ip):
    """Display a setup/config prompt when credentials are missing or invalid."""
    gc.collect()
    group = displayio.Group()
    display.root_group = group
    group.append(
        label.Label(
            terminalio.FONT,
            text=f"Configure Device\n\nUse the GlucoBit app,\nor visit in browser:\nhttp://{ip}/\n\nCheck your Dexcom\ncredentials.",
            color=0xFFAA00,
            anchor_point=(0.5, 0.5),
            anchored_position=(140, 120),
        )
    )
    pixels[0] = (40, 20, 0)
    pixels[1] = (40, 20, 0)
    pixels.show()


# Dexcom API login
def dexcom_login(https_session):
    url = f"https://{DEXCOM_SERVER}/ShareWebServices/Services/General/LoginPublisherAccountByName"
    headers = {"Content-Type": "application/json"}
    payload = f'{{"accountName":"{DEXCOM_USERNAME}","password":"{DEXCOM_PASSWORD}","applicationId":"d89443d2-327c-4a6f-89e5-496bbb0317db"}}'
    r = None
    try:
        r = https_session.post(url, headers=headers, data=payload)
        if r.status_code == 200:
            return r.text.strip('"')
        print(f"Login failed: Status {r.status_code}")
        return None
    except Exception as e:
        print(f"Login error: {e}")
        return None
    finally:
        if r is not None:
            r.close()

def get_glucose(https_session, session_id):
    global last_ssid
    
    url = (
        f"https://{DEXCOM_SERVER}/ShareWebServices/Services/Publisher/ReadPublisherLatestGlucoseValues?sessionID={session_id}&minutes=1440&maxCount=2")
    headers = {"Content-Type": "application/json"}
    r = None
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
    finally:
        if r is not None:
            r.close()

def start_webserver(pool, https_session, ap_mode=False):
    """Start web server with redesigned UI"""
    try:
        server = Server(pool, root_path="/")
    except Exception as e:
        print(f"Failed to initialize server: {e}")
        return None


    # Webpage for settings
    @server.route("/", methods=["GET"])
    def index(request: Request):
        setup_needed = is_setup_needed()
        wizard_banner = '<div class="wizard-banner"><strong>Welcome! Let\'s get you set up.</strong> Complete the steps below to start displaying glucose data on your device.</div>' if setup_needed else ''
        step1 = '<span class="step-badge">1</span>' if setup_needed else ''
        step2 = '<span class="step-badge">2</span>' if setup_needed else ''
        step3 = '<span class="step-badge">3</span>' if setup_needed else ''
        wifi_unconfigured = setup_needed and (not WIFI_SSID or WIFI_SSID == default_settings['WIFI_SSID'])
        dexcom_unconfigured = setup_needed and (not DEXCOM_USERNAME or DISPLAY_NAME == 'DexcomFollowerName')
        wifi_cls = ' section-setup-required' if wifi_unconfigured else ''
        dexcom_cls = ' section-setup-required' if dexcom_unconfigured else ''
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
                input[type="password"],
                input[type="color"],
                select {{
                    width: 100%;
                    padding: 12px 14px;
                    font-size: 15px;
                    border: 1.5px solid #e0e0e0;
                    border-radius: 8px;
                    transition: all 0.3s ease;
                    background: #fafafa;
                }}

                input[type="text"]:focus,
                input[type="password"]:focus,
                input[type="color"]:focus,
                select:focus {{
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

                .wizard-banner {{
                    background: #fff8e1;
                    border: 1.5px solid #f59e0b;
                    border-radius: 10px;
                    padding: 16px 20px;
                    margin-bottom: 24px;
                    color: #78350f;
                    font-size: 14px;
                    line-height: 1.5;
                }}

                .wizard-banner strong {{
                    display: block;
                    font-size: 15px;
                    margin-bottom: 4px;
                    color: #92400e;
                }}

                .step-badge {{
                    display: inline-flex;
                    align-items: center;
                    justify-content: center;
                    width: 22px;
                    height: 22px;
                    border-radius: 50%;
                    background: #667eea;
                    color: white;
                    font-size: 12px;
                    font-weight: 700;
                    margin-right: 8px;
                    vertical-align: middle;
                }}

                .section-setup-required {{
                    border: 2px solid #f59e0b !important;
                    border-radius: 10px;
                    padding: 16px !important;
                    margin: -4px;
                }}

                .btn-reset {{
                    flex: 0 0 auto;
                    padding: 14px 18px;
                    font-size: 14px;
                    font-weight: 500;
                    border: 1.5px solid #d1d5db;
                    border-radius: 8px;
                    cursor: pointer;
                    background: white;
                    color: #6b7280;
                    transition: all 0.2s ease;
                }}

                .btn-reset:hover {{
                    border-color: #9ca3af;
                    color: #374151;
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
                    {wizard_banner}
                    <form method="POST" action="/save">
                        <!-- WiFi Section -->
                        <div class="form-group">
                            <label for="WIFI_SSID">Network Name (SSID)</label>
                            <div style="display:flex; gap:8px; align-items:center;">
                                <input type="text" id="WIFI_SSID" name="WIFI_SSID" 
                                       placeholder="Select your WiFi network" 
                                       value="{WIFI_SSID}" required
                                       list="wifi-networks"
                                       style="flex:1; min-width:0;">
                                <button type="button" id="scan-btn" onclick="scanWifi()"
                                        style="padding:12px 14px; background:#667eea; color:white; 
                                               border:none; border-radius:8px; cursor:pointer; 
                                               font-size:13px; font-weight:600; white-space:nowrap;
                                               flex-shrink:0;">
                                    📡 Scan
                                </button>
                            </div>
                            <div id="scan-status" style="font-size:12px; color:#667eea; margin-top:4px; min-height:16px;"></div>
                            <div id="wifi-list" style="display:none; margin-top:10px; display;flex; flex-direction:column; gap:6px;"></div>
                                <div class="form-group">
                                    <label for="WIFI_PASSWORD">Network Password</label>
                                    <input type="password" id="WIFI_PASSWORD" name="WIFI_PASSWORD" placeholder="Enter your WiFi password" value="{WIFI_PASSWORD}">
                                    <input type="checkbox" onclick="showPasswd()"> Show Password
                                </div>
                        </div>

                        <!-- Dexcom Section -->
                        <div class="section{dexcom_cls}">
                            <div class="section-title">{step2}🩺 Dexcom Account</div>
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
                            <div class="section-title">{step3}🎨 Display Settings</div>
                            <div class="form-group">
                                <label for="DISPLAY_NAME">Display Name</label>
                                <input type="text" id="DISPLAY_NAME" name="DISPLAY_NAME" placeholder="Enter a name for this display" value="{DISPLAY_NAME}">
                            </div>
                            <div class="form-group">
                                <label for="BACKGROUND_COLOR">Background Color (not active yet)</label>
                                <input type="color" id="BACKGROUND_COLOR" name="BACKGROUND_COLOR" value="{BACKGROUND_COLOR}">
                            </div>
                            <div class="form-group">
                                <label for="UI_THEME">Screen UI Style</label>
                                <select id="UI_THEME" name="UI_THEME">
                                    <option value="1" {"selected" if UI_THEME == 1 else ""}>UI 1 - Cards</option>
                                    <option value="2" {"selected" if UI_THEME == 2 else ""}>UI 2 - Split Bands</option>
                                    <option value="3" {"selected" if UI_THEME == 3 else ""}>UI 3 - Minimal</option>
                                </select>
                            </div>
                            <div class="toggle-group">
                                <span class="toggle-label">Mmol/L</span>
                                <label class="toggle">
                                    <input type="checkbox" name="MMOL" {"checked" if MMOL else ""}>
                                    <span class="slider"></span>
                                </label>
                                <span class="toggle-label">Mmol/L</span>
                            </div>
                        </div>

                        <div class="section">
                            <div class="section-title">Alert Settings</div>
                            <div class="form-group">
                                <label for="ALERT_LOW_MGDL">Low Alert (mg/dL)</label>
                                <input type="number" id="ALERT_LOW_MGDL" name="ALERT_LOW_MGDL" min="55" max="120" step="5" value="{ALERT_LOW_MGDL}">
                            </div>
                            <div class="form-group">
                                <label for="ALERT_HIGH_MGDL">High Alert (mg/dL)</label>
                                <input type="number" id="ALERT_HIGH_MGDL" name="ALERT_HIGH_MGDL" min="120" max="300" step="5" value="{ALERT_HIGH_MGDL}">
                            </div>
                        </div>
                        
                        <div class="section">
                            <div class="section-title">Test Settings</div>
                            <div class="toggle-group">
                                <label class="toggle">
                                    <input type="checkbox" name="ALARM_TEST" {"checked" if FORCE_ALARM_TEST else ""}>
                                    <span class="slider"></span>
                                </label>
                                <span class="toggle-label">Alarm test mode</span>
                            </div>
                        </div>
                        <!-- Submit Button -->
                        <div class="button-group">
                            <input type="submit" value="Save Settings">
                            <button type="button" class="btn-reset" onclick="resetSetup()">Restart Setup Wizard</button>
                        </div>
                    </form>
                </div>
                <script>
                function resetSetup() {{
                    fetch('/reset-setup', {{method: 'POST'}})
                        .then(() => window.location.reload())
                        .catch(() => window.location.reload());
                }}
                
                
                function scanWifi() {{
                    const btn = document.getElementById('scan-btn');
                    const status = document.getElementById('scan-status');
                    const list = document.getElementById('wifi-list');

                    btn.disabled = true;
                    btn.textContent = '⏳ Scanning...';
                    status.textContent = 'Scanning for networks...';
                    list.style.display = 'none';
                    list.innerHTML = '';

                    fetch('/scan-wifi')
                        .then(r => r.json())
                        .then(networks => {{
                            if (networks.length === 0) {{
                                status.textContent = 'No networks found. Try again.';
                                return;
                            }}

                            status.textContent = networks.length + ' network(s) found:';
                            list.style.display = 'flex';

                            networks.forEach(n => {{
                                const bars = signalBars(n.rssi);
                                const btn = document.createElement('button');
                                btn.type = 'button';
                                btn.style.cssText = `
                                    display: flex;
                                    justify-content: space-between;
                                    align-items: center;
                                    padding: 10px 14px;
                                    background: #f8f9ff;
                                    border: 1.5px solid #e0e4ff;
                                    border-radius: 8px;
                                    cursor: pointer;
                                    font-size: 14px;
                                    color: #333;
                                    text-align: left;
                                    transition: all 0.15s ease;
                                `;
                                btn.innerHTML = `
                                    <span style="font-weight:500;">${{n.ssid}}</span>
                                    <span style="font-size:12px; color:#888; display:flex; align-items:center; gap:6px;">
                                        <span style="letter-spacing:1px;">${{bars}}</span>
                                        <span>${{n.rssi}} dBm</span>
                                    </span>
                                `;
                                btn.onmouseover = () => btn.style.background = '#eef0ff';
                                btn.onmouseout = () => {{
                                    const selected = document.getElementById('WIFI_SSID').value === n.ssid;
                                    btn.style.background = selected ? '#e8ebff' : '#f8f9ff';
                                    btn.style.borderColor = selected ? '#667eea' : '#e0e4ff';
                                }};
                                btn.onclick = () => {{
                                    document.getElementById('WIFI_SSID').value = n.ssid;
                                    // Highlight selected
                                    list.querySelectorAll('button').forEach(b => {{
                                        b.style.background = '#f8f9ff';
                                        b.style.borderColor = '#e0e4ff';
                                    }});
                                    btn.style.background = '#e8ebff';
                                    btn.style.borderColor = '#667eea';
                                    document.getElementById('WIFI_PASSWORD').focus();
                                }};
                                list.appendChild(btn);
                            }});
                        }})
                        .catch(() => {{
                            status.textContent = 'Scan failed. Check device connection.';
                        }})
                        .finally(() => {{
                            btn.disabled = false;
                            btn.textContent = '📡 Scan';
                        }});
                }}
                
                function showPasswd() {{
                    var x = document.getElementById("WIFI_PASSWORD");
                    if (x.type === "password") {{
                        x.type = "text";
                    }} else {{
                        x.type = "password";
                    }}
                }}

                function signalBars(rssi) {{
                    if (rssi >= -50) return '▂▄▆█';
                    if (rssi >= -60) return '▂▄▆·';
                    if (rssi >= -70) return '▂▄··';
                    return '▂···';
                }}
                </script>
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
        global settings, WIFI_SSID, WIFI_PASSWORD, DEXCOM_USERNAME, DEXCOM_PASSWORD, DEXCOM_SERVER, DISPLAY_NAME, MMOL, UI_THEME, BACKGROUND_COLOR, FORCE_ALARM_TEST, ALERT_LOW_MGDL, ALERT_HIGH_MGDL
        global pending_wifi_reconnect, pending_session_refresh, pending_display_refresh

        form_data = request.form_data
        try:
            theme_value = int(url_decode(form_data.get("UI_THEME", str(UI_THEME))))
        except Exception:
            theme_value = 1
        if theme_value not in (1, 2, 3):
            theme_value = 1

        # Build new settings dict
        new_settings = {
            "WIFI_SSID": url_decode(form_data.get("WIFI_SSID", WIFI_SSID)),
            "WIFI_PASSWORD": url_decode(form_data.get("WIFI_PASSWORD", WIFI_PASSWORD)),
            "DEXCOM_USERNAME": url_decode(form_data.get("DEXCOM_USERNAME", DEXCOM_USERNAME)),
            "DEXCOM_PASSWORD": url_decode(form_data.get("DEXCOM_PASSWORD", DEXCOM_PASSWORD)),
            "DEXCOM_SERVER": url_decode(form_data.get("DEXCOM_SERVER", DEXCOM_SERVER)),
            "DISPLAY_NAME": url_decode(form_data.get("DISPLAY_NAME", DISPLAY_NAME)),
            "BACKGROUND_COLOR": url_decode(form_data.get("BACKGROUND_COLOR", BACKGROUND_COLOR)),
            "MMOL": "MMOL" in form_data,
            "UI_THEME": theme_value,
            "ALERT_LOW_MGDL": form_data.get("ALERT_LOW_MGDL", ALERT_LOW_MGDL),
            "ALERT_HIGH_MGDL": form_data.get("ALERT_HIGH_MGDL", ALERT_HIGH_MGDL),
            "SETUP_MODE": False
        }
        
        FORCE_ALARM_TEST = "ALARM_TEST" in form_data

        # Shared with the BLE settings path: persists, updates globals and
        # queues reconnect/refresh for the main loop.
        ok, wifi_changed = apply_new_settings(new_settings)
        if not ok:
            return Response(
                request,
                "<script>alert('ERROR: Could not write settings.json'); window.location='/';</script>",
                content_type="text/html"
            )

        if wifi_changed:
            msg = "Settings saved. Applying WiFi changes now."
        else:
            msg = "Settings saved and queued for refresh."

        return Response(
            request,
            f"<script>alert('{msg}'); window.location='/';</script>",
            content_type="text/html"
        )
    # ============================================================
    # RESET SETUP ROUTE - Re-enter the setup wizard
    # ============================================================
    @server.route("/reset-setup", methods=["POST"])
    def reset_setup(request: Request):
        global settings, pending_display_refresh
        settings["SETUP_MODE"] = True
        try:
            with open(SETTINGS_FILE, "w") as f:
                json.dump(settings, f)
                f.flush()
                os.sync()
        except Exception as e:
            print("reset-setup write failed:", e)
        pending_display_refresh = True
        return Response(request, "", content_type="text/plain")
    
    
    @server.route("/scan-wifi", methods=["GET"])
    def scan_wifi(request: Request):
        networks = []
        try:
            found = wifi.radio.start_scanning_networks()
            for net in found:
                try:
                    ssid = net.ssid
                    rssi = net.rssi
                    if ssid:  # filter out hidden networks
                        networks.append({"ssid": ssid, "rssi": rssi})
                except Exception:
                    pass
        except Exception as e:
            print("WiFi scan error:", e)
        finally:
            try:
                wifi.radio.stop_scanning_networks()
            except Exception:
                pass

        # Sort by signal strength (strongest first), deduplicate SSIDs
        seen = set()
        unique = []
        for n in sorted(networks, key=lambda x: x["rssi"], reverse=True):
            if n["ssid"] not in seen:
                seen.add(n["ssid"])
                unique.append(n)

        return Response(request, json.dumps(unique), content_type="application/json")
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
    """Robust deep sleep with touch wake – works on all recent CircuitPython"""
    global touch

    print("Preparing for deep sleep...")

    # Deinitisalise touch
    cleanup_touch()
    gc.collect()
    time.sleep(0.5)
    
    # Turn screen off
    screen_off()
    pixels.fill((0,0,0))
    pixels.show()

    # Mark that next boot is from touch wake
    alarm.sleep_memory[0] = 1

    try:
        # Create touch alarm
        touch_alarm = alarm.touch.TouchAlarm(pin=board.A2)

        print("Entering deep sleep – touch A2 to wake")
        alarm.light_sleep_until_alarms(touch_alarm)

        print("Woke up!")  
    except Exception as e:
        print("Sleep setup error:", e)

    time.sleep(0.3)
    gc.collect()

    # Force full reset on startup from boot
    microcontroller.reset()


# -------- MAIN LOOP --------
gc.collect()
print(f"Free memory: {gc.mem_free()} bytes")
pool = socketpool.SocketPool(wifi.radio)
https = adafruit_requests.Session(pool, ssl.create_default_context())
web_server = None  # in case both Wi-Fi and AP fail



# ====================
# Wi-Fi / AP handling 
# ====================
def ensure_network_and_server():
    global web_server, session

    # Try normal Wi-Fi first
    if wifi.radio.connected or connect_to_wifi():
        print("Connected to Wi-Fi:", wifi.radio.ipv4_address)
        for _ in range(30):
            ip = wifi.radio.ipv4_address
            if ip and str(ip) != "0.0.0.0":
                break
            time.sleep(0.5)
        session = dexcom_login(https) or session
        web_server = start_webserver(pool, https, ap_mode=False)
    else:
        # Fall back to AP mode
        start_ap_mode()
        web_server = start_webserver(pool, https, ap_mode=True)
        session = None

ensure_network_and_server()


# ====================
# BLE companion-app link
# ====================
def _ble_on_settings(updates):
    """Settings JSON received from the app — same path as the web /save."""
    ok, _ = apply_new_settings(updates)
    return ok


def _ble_on_glucose(value, trend, ts, prev_value, prev_ts):
    """Reading relayed by the app. Queued for the main loop; ignored (but
    still acked) when we already have an equal or newer reading."""
    global ble_pushed
    if last_reading_epoch is not None and ts <= last_reading_epoch:
        return True
    ble_pushed = (value, trend, ts, prev_value)
    return True


def _ble_get_status():
    flags = 0
    if wifi.radio.connected:
        flags |= 0x01
    if is_setup_needed():
        flags |= 0x02
    age = None
    if last_reading_monotonic is not None:
        age = int(time.monotonic() - last_reading_monotonic)
    # needs_data: no WiFi, or the displayed reading has gone stale
    # (>330 s = two missed 90 s fetch cycles plus margin)
    if not wifi.radio.connected or age is None or age > 330:
        flags |= 0x04
    if alarm_active:
        flags |= 0x08

    try:
        parts = [int(p) for p in get_version().split(".")]
    except Exception:
        parts = []
    while len(parts) < 3:
        parts.append(0)

    return flags, None, age, parts


if settings.get("BLE_ENABLED", True):
    try:
        from app.ble import GlucoBitBLE
        gc.collect()
        _mem_before_ble = gc.mem_free()
        ble_link = GlucoBitBLE(_ble_on_settings, _ble_on_glucose, _ble_get_status)
        gc.collect()
        print(f"BLE enabled (cost {_mem_before_ble - gc.mem_free()} bytes, free {gc.mem_free()})")
    except Exception as e:
        ble_link = None
        print("BLE unavailable:", e)


def apply_pending_settings():
    global pending_wifi_reconnect, pending_session_refresh, pending_display_refresh
    global web_server, pool, https, session, last_fetch_time, last_reading, last_glucose_cache

    if not (pending_wifi_reconnect or pending_session_refresh or pending_display_refresh):
        return

    if pending_wifi_reconnect:
        print("Applying pending WiFi changes...")
        try:
            wifi.radio.stop_ap()
        except Exception:
            pass

        connected = connect_to_wifi()

        # Recreate network objects after WiFi state changes.
        pool = socketpool.SocketPool(wifi.radio)
        https = adafruit_requests.Session(pool, ssl.create_default_context())

        try:
            if web_server:
                web_server.stop()
        except Exception:
            pass

        if connected:
            web_server = start_webserver(pool, https, ap_mode=False)
            print("WiFi reconnect complete; web server restarted in station mode.")
        else:
            start_ap_mode()
            web_server = start_webserver(pool, https, ap_mode=True)
            print("WiFi reconnect failed; web server restarted in AP mode.")

        session = None

    if pending_session_refresh:
        session = None

    if pending_display_refresh:
        if last_glucose_cache is not None:
            show_glucose(*last_glucose_cache)
        else:
            last_fetch_time = 0
            last_reading = None

    pending_wifi_reconnect = False
    pending_session_refresh = False
    pending_display_refresh = False



if wifi.radio.connected:
    try:
        pool = socketpool.SocketPool(wifi.radio)
        
        # NTP Time server setup
        ntp = adafruit_ntp.NTP(pool, tz_offset=0)  
        rtc.RTC().datetime = ntp.datetime
        print("RTC synced to NTP on boot")
        print(time.localtime()) #Print current time - debug
    except Exception as e:
        print("NTP sync failed on boot:", e)


print("Starting main glucose loop")
last_fetch_time = 0
last_update_check = 0
first_fetch = True
first_check = True

# Main while loop
while True:
    gc.collect()
    apply_pending_settings()
   
    # Create Time 
    if time_label is not None:
        t = time.localtime()
        time_label.text = f"{t.tm_hour:02d}:{t.tm_min:02d}:{t.tm_sec:02d}"

    # Glucose Fetch
    if wifi.radio.connected and (time.monotonic() - last_fetch_time >= 90 or first_fetch): # Checks if WiFi is connected and last fetch was >90 secs
        first_fetch = False
        points = get_glucose(https, session)
        if points and len(points) == 3:
            (value, trend), (prev_value, _), latest_reading_time = points
            epoch = wt_to_epoch(latest_reading_time)
            # Never clobber a newer BLE-relayed reading with a stale fetch.
            if epoch is None or last_reading_epoch is None or epoch >= last_reading_epoch:
                last_glucose_cache = (value, trend, latest_reading_time, prev_value)
                show_glucose(value, trend, latest_reading_time, prev_value)
                if epoch is not None:
                    last_reading_epoch = epoch
                last_reading_monotonic = time.monotonic()
        else:
            session = dexcom_login(https) or session
            if is_setup_needed():
                ip = str(wifi.radio.ipv4_address or wifi.radio.ipv4_address_ap or "192.168.4.1")
                show_setup_screen(ip)
            else:
                show_glucose(None, None, None)
        last_fetch_time = time.monotonic()

    # Reading relayed from the companion app over BLE (typically while WiFi
    # is down, but also when fetches are failing and the reading went stale)
    if ble_pushed is not None:
        value, trend, ts, prev_value = ble_pushed
        ble_pushed = None
        if last_reading_epoch is None or ts > last_reading_epoch:
            print(f"BLE reading received: {value} mg/dL ({trend})")
            last_glucose_cache = (value, trend, ts, prev_value)
            show_glucose(value, trend, ts, prev_value)
            last_reading_epoch = ts
            last_reading_monotonic = time.monotonic()

    if wifi.radio.connected and (time.monotonic() - last_update_check >= version_check or first_check):
        last_update_check = time.monotonic()
        first_check = False

        try:
            if check_and_update(get_version(), https):
                print("OTA update applied — rebooting...")
                import microcontroller
                microcontroller.reset()
        except Exception as e:
            print("OTA check error:", e)

        
        

    # Debug Webserver
    if web_server:
        try:
            web_server.poll()
        except Exception as e:
            print("Web server poll error:", e)

    if ble_link:
        try:
            ble_link.poll()
            ble_link.notify_status()
        except Exception as e:
            print("BLE poll error:", e)

    if touch and touch.value: # check for touch
        print("Touch Detected")
        time.sleep(0.3)
        attempt_sleep()

    time.sleep(0.1)
