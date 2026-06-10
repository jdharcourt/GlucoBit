import wifi
import time

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
ssid = settings["WIFI_SSID"]
password = settings["WIFI_PASSWORD"]

def connect(ssid, password, timeout=15):
    wifi.radio.connect(ssid, password)
    start = time.monotonic()
    while not wifi.radio.ipv4_address:
        if time.monotonic() - start > timeout:
            raise RuntimeError("WiFi timeout")
        time.sleep(0.1)
