"""
server/main.py
EXE 進入點 — Console 視窗啟動後自動縮到最小
"""

import sys
import os
import logging
import threading
import time
import signal

# ── 設定 logging ──────────────────────────
logging.basicConfig(
    level=logging.WARNING,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)

HOST = "127.0.0.1"
PORT = 7070


def minimize_console():
    """Windows：啟動後將 console 視窗縮到最小"""
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
    port_str = arduino_port or "未偵測到"
    print(f"""
╔══════════════════════════════════════╗
║     Servo Controller Server          ║
╠══════════════════════════════════════╣
║  Web UI : http://{HOST}:{PORT}         ║
║  API    : http://{HOST}:{PORT}/docs    ║
╠══════════════════════════════════════╣
║  Arduino: {port_str:<28}║
╚══════════════════════════════════════╝
  按 Ctrl+C 停止
""")


def main():
    # 延遲 0.5 秒後縮小視窗（讓 banner 先顯示）
    threading.Timer(0.5, minimize_console).start()

    # 建立 app
    sys.path.insert(0, os.path.dirname(__file__))
    from server import create_app
    from serial_manager import SerialManager

    app, serial_mgr, _ = create_app()

    # 自動偵測 Arduino
    port = SerialManager.auto_detect()
    if port:
        ok = serial_mgr.connect(port)
        if ok:
            print(f"[OK] Arduino 已連線：{port}")
        else:
            print(f"[!!] Arduino 連線失敗：{port}")
    else:
        print("[--] 未偵測到 Arduino，請在 Web UI 手動連線")

    print_banner(port)

    # Serial 狀態更新 callback（console 顯示）
    original_on_line = serial_mgr._on_line
    def on_line_with_log(line: str):
        if line.startswith("ERR"):
            print(f"[Arduino ERR] {line}")
        if original_on_line:
            original_on_line(line)
    serial_mgr.on_line(on_line_with_log)

    # Ctrl+C 處理
    def on_stop(sig, frame):
        print("\n[停止] 正在關閉…")
        serial_mgr.disconnect()
        sys.exit(0)

    signal.signal(signal.SIGINT,  on_stop)
    signal.signal(signal.SIGTERM, on_stop)

    # 啟動 uvicorn
    import uvicorn
    uvicorn.run(app, host=HOST, port=PORT, log_level="warning")


if __name__ == "__main__":
    main()
