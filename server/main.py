"""
server/main.py
EXE entry point — minimizes the console window after startup
"""

import sys
import os
import logging
import threading
import time
import signal

# ── Configure logging ──────────────────────────
logging.basicConfig(
    level=logging.WARNING,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)

HOST = "127.0.0.1"
PORT = 7070


def minimize_console():
    """Windows: minimize the console window after startup"""
    if sys.platform != "win32":
        return
    try:
        import ctypes
        hwnd = ctypes.windll.kernel32.GetConsoleWindow()
        if hwnd:
            # SW_MINIMIZE = 6
            ctypes.windll.user32.ShowWindow(hwnd, 6)
    except Exception:
        pass


def print_banner(arduino_port: str = None):
    port_str = arduino_port or "Not detected"
    print(f"""
╔══════════════════════════════════════╗
║     Servo Controller Server          ║
╠══════════════════════════════════════╣
║  Web UI : http://{HOST}:{PORT}      ║
║  API    : http://{HOST}:{PORT}/docs ║
╠══════════════════════════════════════╣
║  Arduino: {port_str:<28}  ║
╚══════════════════════════════════════╝
  Press Ctrl+C to stop
""")


def main():
    # Delay 0.5s before minimizing (let the banner print first)
    threading.Timer(0.5, minimize_console).start()

    # Create app
    sys.path.insert(0, os.path.dirname(__file__))
    from server import create_app
    from serial_manager import SerialManager

    app, serial_mgr, _ = create_app()

    # Auto-detect Arduino
    port = SerialManager.auto_detect()
    if port:
        ok = serial_mgr.connect(port)
        if ok:
            print(f"[OK] Arduino connected: {port}")
        else:
            print(f"[!!] Arduino connection failed: {port}")
    else:
        print("[--] Arduino not detected, please connect manually via Web UI")

    print_banner(port)

    # Serial status update callback (console output)
    original_on_line = serial_mgr._on_line
    def on_line_with_log(line: str):
        if line.startswith("ERR"):
            print(f"[Arduino ERR] {line}")
        if original_on_line:
            original_on_line(line)
    serial_mgr.on_line(on_line_with_log)

    # Handle Ctrl+C
    def on_stop(sig, frame):
        print("\n[Stopping] Shutting down…")
        serial_mgr.disconnect()
        sys.exit(0)

    signal.signal(signal.SIGINT,  on_stop)
    signal.signal(signal.SIGTERM, on_stop)

    # Start uvicorn
    import uvicorn
    uvicorn.run(app, host=HOST, port=PORT, log_level="warning")


if __name__ == "__main__":
    main()
