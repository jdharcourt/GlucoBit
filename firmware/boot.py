import storage
import supervisor

# Settings now persist to microcontroller.nvm (see app/main.py), so the
# filesystem no longer has to be device-writable just to save settings.
#
# We only hand filesystem write access to CircuitPython when there is NO USB
# host attached -- i.e. the device is running on battery/charger in the field --
# so that OTA updates (ota.py) can still write code files. When the board is
# plugged into a computer we leave the host in control, so you can push code
# from the Mac without the boot.bak rename dance. Settings still save to NVM in
# either mode.
if not supervisor.runtime.usb_connected:
    storage.remount("/", readonly=False)
