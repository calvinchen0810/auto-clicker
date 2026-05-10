"""
server/serial_manager.py
PySerial 通訊層 — 管理連線、收發、狀態追蹤
支援多 Servo ATTACH / DETACH
"""

import serial
import serial.tools.list_ports
import threading
import logging
import time
from typing import Callable, Optional

logger = logging.getLogger(__name__)

MAX_SERVOS = 6


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

        # 本地追蹤已 ATTACH 的 Servo {sid: pin}
        self._attached: dict[int, int] = {}

        # Events signalled when Arduino confirms OK ATTACH for each sid
        self._attach_events: dict[int, threading.Event] = {}

        self._on_line:       Optional[Callable[[str], None]] = None
        self._on_disconnect: Optional[Callable[[], None]]    = None

    # ── 回調 ──────────────────────────────

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
            ports.append({"port": p.device, "desc": desc, "likely": likely})
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
        self._serial   = None
        self._attached = {}
        logger.info("Disconnected")

    @property
    def is_connected(self) -> bool:
        return self._serial is not None and self._serial.is_open

    @property
    def port(self) -> Optional[str]:
        return self._serial.port if self.is_connected else None

    @property
    def attached(self) -> dict[int, int]:
        """回傳已 ATTACH 的 Servo {sid: pin}"""
        return dict(self._attached)

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

    # ── Servo ATTACH / DETACH ─────────────

    def attach_servo(self, sid: int, pin: int) -> bool:
        """送出 ATTACH sid pin，更新本地狀態"""
        if not self.is_connected:
            return False
        if not (1 <= sid <= MAX_SERVOS):
            return False
        ok = self.send(f"ATTACH {sid} {pin}")
        if ok:
            self._attached[sid] = pin
        return ok

    def attach_servo_and_wait(self, sid: int, pin: int, timeout: float = 3.0) -> bool:
        """送出 ATTACH sid pin，然後阻塞等待 Arduino 回應 OK ATTACH 或逾時"""
        if not self.is_connected:
            return False
        if not (1 <= sid <= MAX_SERVOS):
            return False
        evt = threading.Event()
        self._attach_events[sid] = evt
        ok = self.send(f"ATTACH {sid} {pin}")
        if not ok:
            self._attach_events.pop(sid, None)
            return False
        confirmed = evt.wait(timeout=timeout)
        self._attach_events.pop(sid, None)
        if confirmed:
            self._attached[sid] = pin
        else:
            logger.warning(f"attach_servo_and_wait: timeout waiting for OK ATTACH sid={sid}")
            # Assume attached anyway so script can proceed
            self._attached[sid] = pin
        return True

    def detach_servo(self, sid: int) -> bool:
        """送出 DETACH sid，更新本地狀態"""
        if not self.is_connected:
            return False
        ok = self.send(f"DETACH {sid}")
        if ok:
            self._attached.pop(sid, None)
        return ok

    def attach_all(self, pin_map: dict[int, int]) -> bool:
        """批次 ATTACH，pin_map = {sid: pin}"""
        for sid, pin in pin_map.items():
            if not self.attach_servo(sid, pin):
                return False
            time.sleep(0.15)
        return True

    def detach_all(self) -> bool:
        """批次 DETACH 所有已 ATTACH 的 Servo"""
        for sid in list(self._attached.keys()):
            self.detach_servo(sid)
            time.sleep(0.1)
        return True

    # ── 腳本傳送 ──────────────────────────

    def send_script(self, steps: list[dict], loop: bool = False) -> bool:
        """
        傳送完整腳本給 Arduino
        steps: [{
            "delay_ms": int,
            "servo_id": int,   ← 新增
            "angle": int,
            "speed": int,
            "duration_ms": int,
            "home": int
        }, ...]
        """
        def _int(v, default=0):
            try:
                return int(v)
            except (TypeError, ValueError):
                return default

        cmds = [
            f"LOOP {'1' if loop else '0'}",
            f"BEGIN {len(steps)}",
        ]
        for s in steps:
            delay_ms = max(0,   min(65535, _int(s.get("delay_ms",    0),    0)))
            sid      = max(1,   min(6,     _int(s.get("servo_id",    1),    1)))
            angle    = max(0,   min(180,   _int(s.get("angle",       90),  90)))
            speed    = max(1,   min(100,   _int(s.get("speed",       60),  60)))
            duration = max(0,   min(65535, _int(s.get("duration_ms", 300), 300)))
            home     = 1 if _int(s.get("home", 1), 1) else 0
            cmds.append(f"STEP {delay_ms} {sid} {angle} {speed} {duration} {home}")
        cmds.append("END")

        for cmd in cmds:
            if not self.send(cmd):
                return False
            time.sleep(0.06)
        return True

    def send_command(self, step: dict) -> bool:
        """送出單一步驟（包成 BEGIN 1 ... END）"""
        return self.send_script([step], loop=False)

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
                        # 同步本地 ATTACH 狀態
                        self._sync_attach_state(line)
                        if self._on_line:
                            self._on_line(line)
            except serial.SerialException as e:
                logger.error(f"Read error: {e}")
                break

        if self._on_disconnect:
            self._on_disconnect()

    def _sync_attach_state(self, line: str):
        """解析 Arduino 回應，同步本地 ATTACH 狀態"""
        # OK ATTACH sid pin
        if line.startswith("OK ATTACH "):
            parts = line.split()
            if len(parts) >= 4:
                try:
                    confirmed_sid = int(parts[2])
                    self._attached[confirmed_sid] = int(parts[3])
                    # Signal any waiting attach_servo_and_wait call
                    evt = self._attach_events.get(confirmed_sid)
                    if evt:
                        evt.set()
                except ValueError:
                    pass
        # OK DETACH sid
        elif line.startswith("OK DETACH "):
            parts = line.split()
            if len(parts) >= 3:
                try:
                    self._attached.pop(int(parts[2]), None)
                except ValueError:
                    pass
        # OK IDLE ATTACHED=1,2,3
        elif line.startswith("OK IDLE") and "ATTACHED=" in line:
            try:
                part = line.split("ATTACHED=")[1].strip()
                if part == "0":
                    self._attached = {}
                # 注意：只知道 sid，不知道 pin，保留已知的 pin
            except Exception:
                pass
