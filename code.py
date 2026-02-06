
try:
    from app.main import run   # renamed from main() to run() or start()
    run()
except Exception as e:
    print("Startup failed:", e)
    import supervisor
    supervisor.runtime.usb_connected  # just to keep it alive if connected
    while True:
        pass
