"""
server/serial_manager.py
PySerial 通訊層 — 管理連線、收發、狀態追蹤
"""

import serial
import serial.tools.list_ports
import threading
import logging
from typing import Callable, Optional

logger = logging.getLogger(__name__)


class SerialManager:
    """
    Arduino Serial 通訊管理器
    線程安全，支援背景讀取與回調通知
    """

    BAUD = 115200

    def __init__(self):
        self._serial:   Optional[serial.Serial] = None
        self._thread:   Optional[threading.Thread] = None
        self._running = False

        # 回調
        self._on_line:  Optional[Callable[[str], None]] = None  # 收到一行
        self._on_disconnect: Optional[Callable[[], None]] = None  # 連線中斷

    # ── 回調設定 ──────────────────────────

    def on_line(self, cb: Callable[[str], None]):
        self._on_line = cb

    def on_disconnect(self, cb: Callable[[], None]):
        self._on_disconnect = cb

    # ── Port 掃描 ─────────────────────────

    @staticmethod
    def scan_ports() -> list[dict]:
        ports = []
        for p in serial.tools.list_ports.comports():
            desc   = p.description or ""
            likely = any(k in desc.upper()
                         for k in ["CH340", "CH341", "ARDUINO", "USB SERIAL"])
            ports.append({
                "port":   p.device,
                "desc":   desc,
                "likely": likely,
            })
        return sorted(ports, key=lambda x: (not x["likely"], x["port"]))

    @staticmethod
    def auto_detect() -> Optional[str]:
        for p in SerialManager.scan_ports():
            if p["likely"]:
                return p["port"]
        return None

    # ── 連線管理 ──────────────────────────

    def connect(self, port: str) -> bool:
        self.disconnect()
        try:
            self._serial  = serial.Serial(port, self.BAUD, timeout=0.1)
            self._running = True
            self._thread  = threading.Thread(
                target=self._read_loop, daemon=True, name="SerialReader"
            )
            self._thread.start()
            logger.info(f"Connected to {port}")
            return True
        except serial.SerialException as e:
            logger.error(f"Connect failed: {e}")
            self._serial = None
            return False

    def disconnect(self):
        self._running = False
        if self._serial and self._serial.is_open:
            try:
                self._serial.close()
            except Exception:
                pass
        self._serial = None
        logger.info("Disconnected")

    @property
    def is_connected(self) -> bool:
        return self._serial is not None and self._serial.is_open

    @property
    def port(self) -> Optional[str]:
        return self._serial.port if self.is_connected else None

    # ── 傳送 ──────────────────────────────

    def send(self, cmd: str) -> bool:
        if not self.is_connected:
            return False
        try:
            self._serial.write((cmd.strip() + "\n").encode())
            logger.debug(f">> {cmd}")
            return True
        except serial.SerialException as e:
            logger.error(f"Send error: {e}")
            return False

    def send_script(self, steps: list[dict], loop: bool = False) -> bool:
        """
        傳送完整腳本給 Arduino
        steps: [{"delay_ms":..., "angle":..., "speed":...,
                 "duration_ms":..., "home":...}, ...]
        """
        cmds = [
            f"LOOP {'1' if loop else '0'}",
            f"BEGIN {len(steps)}",
        ]
        for s in steps:
            home = int(s.get("home", 1))
            cmds.append(
                f"STEP {s['delay_ms']} {s['angle']} "
                f"{s['speed']} {s['duration_ms']} {home}"
            )
        cmds.append("END")

        import time
        for cmd in cmds:
            if not self.send(cmd):
                return False
            time.sleep(0.06)
        return True

    # ── 背景讀取 ──────────────────────────

    def _read_loop(self):
        while self._running:
            try:
                if not self._serial or not self._serial.is_open:
                    break
                raw = self._serial.readline()
                if raw:
                    line = raw.decode("utf-8", errors="replace").strip()
                    if line:
                        logger.debug(f"<< {line}")
                        if self._on_line:
                            self._on_line(line)
            except serial.SerialException as e:
                logger.error(f"Read error: {e}")
                break

        # 連線中斷通知
        if self._on_disconnect:
            self._on_disconnect()
