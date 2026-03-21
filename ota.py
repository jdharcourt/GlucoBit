import os
import ssl
import microcontroller
import wifi
import socketpool
import adafruit_requests

BASE_URL = "https://github.com/jdharcourt/GlucoBit/releases/latest/download"
MANIFEST_URL = BASE_URL + "/release.json"

def _ver(v):
    return tuple(int(x) for x in v.split("."))

def check_and_update(current_version, requests=None):
    if requests is None:
        pool = socketpool.SocketPool(wifi.radio)
        requests = adafruit_requests.Session(pool, ssl.create_default_context())
    
    r = None
    try:
        r = requests.get(MANIFEST_URL)
        manifest = r.json()
    except Exception as e:
        print("Failed to fetch manifest:", e)
        return False
    finally:
        if r is not None:
            r.close()

    if _ver(manifest["version"]) <= _ver(current_version):
        print("Up to Date")
        return False

    print("OTA: new version", manifest["version"])

    if not _exists("/_update"):
        os.mkdir("/_update")

    try:
        for dest, src in manifest["files"].items():
            url = BASE_URL + "/" + src
            path = "/_update/" + dest
            _download(requests, url, path)
        
        _apply()
        return True
    
    except Exception as e:
        print("OTA update failed during download/apply:", e)
        # Optional: clean up partial update
        _rmtree("/_update")
        return False

def _download(req, url, path):
    _mkdirs(path.rsplit("/", 1)[0])
    r = req.get(url, stream=True)
    try:
        with open(path, "wb") as f:
            for chunk in r.iter_content(1024):
                if chunk:
                    f.write(chunk)
                    f.flush()
    finally:
        r.close()

def _apply():
    # Copy all files from /_update to root (overwriting)
    _copytree("/_update", "/")
    
    # Clean up the temp folder
    _rmtree("/_update")

def _copytree(src_dir, dst_dir):
    """Recursively copy contents of src_dir into dst_dir"""
    for item in os.listdir(src_dir):
        src_path = src_dir + "/" + item
        dst_path = dst_dir + "/" + item if dst_dir != "/" else "/" + item
        
        try:
            stat = os.stat(src_path)
            if stat[0] & 0o40000:  # is directory (S_ISDIR check using mode)
                if not _exists(dst_path):
                    os.mkdir(dst_path)
                _copytree(src_path, dst_path)
            else:
                # File: copy by reading/writing
                with open(src_path, "rb") as src_f:
                    with open(dst_path, "wb") as dst_f:
                        while True:
                            chunk = src_f.read(1024)
                            if not chunk:
                                break
                            dst_f.write(chunk)
                # Optional: os.remove(src_path) here if you want immediate delete
        except OSError as e:
            print("Copy error:", src_path, e)
            raise

def _rmtree(path):
    """Recursively delete directory and contents"""
    try:
        for item in os.listdir(path):
            item_path = path + "/" + item
            try:
                stat = os.stat(item_path)
                if stat[0] & 0o40000:  # directory
                    _rmtree(item_path)
                else:
                    os.remove(item_path)
            except OSError:
                pass  # skip if already gone
        os.rmdir(path)
    except OSError as e:
        print("rmtree error on", path, ":", e)

# Your helpers (unchanged)
def _exists(p):
    try:
        os.stat(p)
        return True
    except OSError:
        return False

def _mkdirs(p):
    cur = ""
    for part in p.split("/"):
        if part:
            cur += "/" + part
            if not _exists(cur):
                os.mkdir(cur)
