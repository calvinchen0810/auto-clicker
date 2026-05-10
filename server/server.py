"""
server/server.py
FastAPI + WebSocket 伺服器（多 Servo 支援）
"""

import asyncio
import json
import logging
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional

import uvicorn
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, field_validator

from serial_manager import SerialManager, MAX_SERVOS

logger = logging.getLogger(__name__)

HOST = "127.0.0.1"
PORT = 7070


def print_banner(arduino_port: Optional[str] = None, host: str = HOST, port: int = PORT):
        port_str = arduino_port or "Not detected"
        print(f"""
╔══════════════════════════════════════╗
║     Servo Controller Server          ║
╠══════════════════════════════════════╣
║  Web UI : http://{host}:{port}         ║
║  API    : http://{host}:{port}/docs    ║
╠══════════════════════════════════════╣
║  Arduino: {port_str:<28}║
╚══════════════════════════════════════╝
    Press Ctrl+C to stop
""")


def _html_path() -> Path:
    import sys
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).parent))
    return base / "static" / "index.html"


# ─────────────────────────────────────────
#  Pydantic 模型
# ─────────────────────────────────────────

class StepModel(BaseModel):
    delay_ms:    int = Field(0,  ge=0)
    servo_id:    int = Field(1,  ge=1, le=6)
    angle:       int = Field(90, ge=0, le=180)
    speed:       int = Field(60, ge=1, le=100)
    duration_ms: int = Field(300, ge=0)
    home:        int = Field(1,  ge=0, le=1)

class RunRequest(BaseModel):
    steps: list[StepModel] = Field(default_factory=list, max_length=48)
    loop:  bool = Field(False)
    servos: dict[str, int] = Field(default_factory=dict)
    attach_cmds: list[str] = Field(default_factory=list, max_length=48)

    @field_validator("steps")
    @classmethod
    def steps_len_ok(cls, v):
        return v

class ConnectRequest(BaseModel):
    port: Optional[str] = None

class AttachRequest(BaseModel):
    sid: int = Field(..., ge=1, le=6, description="Servo ID 1–6")
    pin: int = Field(..., ge=2, le=13, description="Arduino 腳位")

class AttachAllRequest(BaseModel):
    # {sid: pin} 例如 {"1": 9, "2": 10}
    servos: dict[str, int]

class DetachRequest(BaseModel):
    sid: int = Field(..., ge=1, le=6)


# ─────────────────────────────────────────
#  WebSocket 管理器
# ─────────────────────────────────────────

class WSManager:
    def __init__(self):
        self._clients: list[WebSocket] = []
        self._lock = asyncio.Lock()
        self._loop: asyncio.AbstractEventLoop | None = None

    def set_loop(self, loop):
        self._loop = loop

    async def connect(self, ws: WebSocket):
        await ws.accept()
        async with self._lock:
            self._clients.append(ws)

    async def disconnect(self, ws: WebSocket):
        async with self._lock:
            self._clients = [c for c in self._clients if c is not ws]

    async def broadcast(self, data: dict):
        if not self._clients:
            return
        msg  = json.dumps(data, ensure_ascii=False)
        dead = []
        async with self._lock:
            clients = list(self._clients)
        for ws in clients:
            try:
                await ws.send_text(msg)
            except Exception:
                dead.append(ws)
        for ws in dead:
            await self.disconnect(ws)

    def broadcast_sync(self, data: dict):
        try:
            loop = self._loop
            if loop is not None and loop.is_running():
                asyncio.run_coroutine_threadsafe(self.broadcast(data), loop)
        except Exception:
            pass


# ─────────────────────────────────────────
#  App 建構
# ─────────────────────────────────────────

def create_app() -> tuple[FastAPI, SerialManager, WSManager]:
    serial_mgr = SerialManager()
    ws_mgr     = WSManager()
    
    # Define lifespan handler first
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        # Startup
        ws_mgr.set_loop(asyncio.get_running_loop())
        yield
        # Shutdown (if needed)
    
    app        = FastAPI(title="Servo Controller", version="1.0.0", lifespan=lifespan)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"], allow_methods=["*"], allow_headers=["*"],
    )

    # ── Serial 回調 → WS 廣播 ────────────
    def on_serial_line(line: str):
        ws_mgr.broadcast_sync({"type": "serial", "line": line})

        if line.startswith("OK RUNNING ") and "/" in line:
            try:
                cur, tot = line.split()[-1].split("/")
                ws_mgr.broadcast_sync({
                    "type": "status", "state": "running",
                    "step": max(0, int(cur) - 1), "total": int(tot),
                    "port": serial_mgr.port,
                })
            except Exception:
                pass
        elif line == "OK DONE":
            ws_mgr.broadcast_sync({"type": "done", "state": "idle"})
        elif line in ("OK STOPPED", "OK READY"):
            ws_mgr.broadcast_sync({"type": "status", "state": "idle",
                                    "port": serial_mgr.port,
                                    "attached": serial_mgr.attached})
        elif line.startswith("OK ATTACH ") or line.startswith("OK DETACH "):
            # 廣播最新 attached 狀態
            ws_mgr.broadcast_sync({
                "type":     "attached",
                "attached": serial_mgr.attached,
            })
        elif line.startswith("OK IDLE") and "ATTACHED=" in line:
            ws_mgr.broadcast_sync({
                "type":     "attached",
                "attached": serial_mgr.attached,
            })
        elif line.startswith("ERR"):
            ws_mgr.broadcast_sync({"type": "error", "message": line})

    def on_disconnect():
        ws_mgr.broadcast_sync({"type": "status", "state": "disconnected",
                                "port": None, "attached": {}})

    serial_mgr.on_line(on_serial_line)
    serial_mgr.on_disconnect(on_disconnect)

    # ── WebSocket /ws ─────────────────────
    @app.websocket("/ws")
    async def ws_endpoint(ws: WebSocket):
        await ws_mgr.connect(ws)
        await ws.send_text(json.dumps(_status(serial_mgr)))
        try:
            while True:
                data = await ws.receive_text()
                msg  = json.loads(data)
                if msg.get("type") == "ping":
                    await ws.send_text(json.dumps({"type": "pong"}))
        except WebSocketDisconnect:
            await ws_mgr.disconnect(ws)

    # ── GET / ─────────────────────────────
    @app.get("/", response_class=HTMLResponse)
    async def index():
        p = _html_path()
        if not p.exists():
            return HTMLResponse("<h1>index.html not found</h1>", status_code=500)
        return HTMLResponse(p.read_text(encoding="utf-8"))

    # ── GET /api/ports ────────────────────
    @app.get("/api/ports")
    async def api_ports():
        return {"ports": SerialManager.scan_ports()}

    # ── GET /api/status ───────────────────
    @app.get("/api/status")
    async def api_status():
        return _status(serial_mgr)

    # ── POST /api/connect ─────────────────
    @app.post("/api/connect")
    async def api_connect(req: ConnectRequest = ConnectRequest()):
        port = req.port or SerialManager.auto_detect()
        if not port:
            raise HTTPException(400, "找不到 Arduino，請指定 COM port")
        ok = await asyncio.get_event_loop().run_in_executor(
            None, serial_mgr.connect, port
        )
        if not ok:
            raise HTTPException(500, f"無法連線到 {port}")
        ws_mgr.broadcast_sync({"type": "status", "state": "idle",
                                "port": port, "attached": {}})
        # 連線後查詢狀態，同步 ATTACH 資訊
        serial_mgr.send("STATUS")
        return {"ok": True, "port": port}

    # ── POST /api/disconnect ──────────────
    @app.post("/api/disconnect")
    async def api_disconnect():
        serial_mgr.disconnect()
        return {"ok": True}

    # ── POST /api/attach ──────────────────
    @app.post("/api/attach")
    async def api_attach(req: AttachRequest):
        if not serial_mgr.is_connected:
            raise HTTPException(400, "尚未連線到 Arduino")
        ok = await asyncio.get_event_loop().run_in_executor(
            None, lambda: serial_mgr.attach_servo(req.sid, req.pin)
        )
        if not ok:
            raise HTTPException(500, "ATTACH 失敗")
        return {"ok": True, "sid": req.sid, "pin": req.pin,
                "attached": serial_mgr.attached}

    # ── POST /api/detach ──────────────────
    @app.post("/api/detach")
    async def api_detach(req: DetachRequest):
        if not serial_mgr.is_connected:
            raise HTTPException(400, "尚未連線到 Arduino")
        ok = await asyncio.get_event_loop().run_in_executor(
            None, lambda: serial_mgr.detach_servo(req.sid)
        )
        if not ok:
            raise HTTPException(500, "DETACH 失敗")
        return {"ok": True, "sid": req.sid, "attached": serial_mgr.attached}

    # ── POST /api/attach_all ──────────────
    @app.post("/api/attach_all")
    async def api_attach_all(req: AttachAllRequest):
        if not serial_mgr.is_connected:
            raise HTTPException(400, "尚未連線到 Arduino")
        pin_map = {int(k): v for k, v in req.servos.items()}
        ok = await asyncio.get_event_loop().run_in_executor(
            None, lambda: serial_mgr.attach_all(pin_map)
        )
        if not ok:
            raise HTTPException(500, "ATTACH_ALL 失敗")
        return {"ok": True, "attached": serial_mgr.attached}

    # ── POST /api/detach_all ──────────────
    @app.post("/api/detach_all")
    async def api_detach_all():
        if not serial_mgr.is_connected:
            raise HTTPException(400, "尚未連線到 Arduino")
        await asyncio.get_event_loop().run_in_executor(
            None, serial_mgr.detach_all
        )
        return {"ok": True, "attached": {}}

    # ── POST /api/run ─────────────────────
    @app.post("/api/run")
    async def api_run(req: RunRequest):
        if not serial_mgr.is_connected:
            raise HTTPException(400, "尚未連線到 Arduino")

        if not req.steps and not req.attach_cmds:
            raise HTTPException(400, "steps 與 attach_cmds 不能同時為空")

        # Optional pre-attach commands, useful for two-phase execution.
        for raw in req.attach_cmds:
            if not isinstance(raw, str):
                continue
            cmd = raw.strip()
            parts = cmd.split()
            if len(parts) != 3 or parts[0].upper() != "ATTACH":
                continue
            try:
                sid = int(parts[1])
                pin = int(parts[2])
            except ValueError:
                continue
            if not (1 <= sid <= MAX_SERVOS and 2 <= pin <= 13):
                continue
            if serial_mgr.attached.get(sid) == pin:
                continue
            ok_attach_cmd = await asyncio.get_event_loop().run_in_executor(
                None, lambda sid=sid, pin=pin: serial_mgr.attach_servo_and_wait(sid, pin)
            )
            if not ok_attach_cmd:
                raise HTTPException(500, f"attach_cmd 執行失敗 sid={sid} pin={pin}")

        steps = [s.model_dump() for s in req.steps]

        # Auto-attach servos used in this script before RUN.
        used_sids = sorted({int(s.get("servo_id", 1)) for s in steps})

        req_pin_map: dict[int, int] = {}
        for k, v in (req.servos or {}).items():
            try:
                sid = int(k)
                pin = int(v)
            except (TypeError, ValueError):
                continue
            if 1 <= sid <= MAX_SERVOS and 2 <= pin <= 13:
                req_pin_map[sid] = pin

        # Priority: request mapping > currently attached mapping
        effective_pin_map: dict[int, int] = dict(serial_mgr.attached)
        effective_pin_map.update(req_pin_map)

        missing_sids: list[int] = []
        auto_attached_count = 0
        for sid in used_sids:
            if sid in serial_mgr.attached:
                continue

            pin = effective_pin_map.get(sid)
            if pin is None:
                missing_sids.append(sid)
                continue

            ok_attach = await asyncio.get_event_loop().run_in_executor(
                None, lambda sid=sid, pin=pin: serial_mgr.attach_servo_and_wait(sid, pin)
            )
            if not ok_attach:
                raise HTTPException(500, f"自動 ATTACH 失敗 sid={sid} pin={pin}")
            auto_attached_count += 1

        if missing_sids:
            raise HTTPException(
                400,
                "缺少 servo mapping，請在 JSON 提供 servos 或先手動 ATTACH: "
                + ",".join(str(sid) for sid in missing_sids),
            )

        ws_mgr.broadcast_sync({
            "type": "attached",
            "attached": serial_mgr.attached,
        })

        if not steps:
            return {
                "ok": True,
                "attach_only": True,
                "attached": serial_mgr.attached,
            }

        # attach_servo_and_wait already blocks until Arduino confirms OK ATTACH,
        # so no additional settle delay is needed.

        ok = await asyncio.get_event_loop().run_in_executor(
            None, lambda: serial_mgr.send_script(steps, req.loop)
        )
        if not ok:
            raise HTTPException(500, "腳本傳送失敗")
        ws_mgr.broadcast_sync({
            "type": "status", "state": "running",
            "step": 0, "total": len(steps), "port": serial_mgr.port,
        })
        return {"ok": True, "steps": len(steps), "loop": req.loop}

    # ── POST /api/stop ────────────────────
    @app.post("/api/stop")
    async def api_stop():
        if not serial_mgr.is_connected:
            raise HTTPException(400, "尚未連線")
        serial_mgr.send("STOP")
        return {"ok": True}

    # ── POST /api/command ─────────────────
    @app.post("/api/command")
    async def api_command(req: StepModel):
        if not serial_mgr.is_connected:
            raise HTTPException(400, "尚未連線")
        ok = await asyncio.get_event_loop().run_in_executor(
            None, lambda: serial_mgr.send_command(req.model_dump())
        )
        if not ok:
            raise HTTPException(500, "指令傳送失敗")
        return {"ok": True}

    # ── POST /api/send ────────────────────
    @app.post("/api/send")
    async def api_send(body: dict):
        if not serial_mgr.is_connected:
            raise HTTPException(400, "尚未連線")
        cmd = body.get("cmd", "").strip()
        if not cmd:
            raise HTTPException(400, "cmd 不能為空")
        serial_mgr.send(cmd)
        return {"ok": True}

    return app, serial_mgr, ws_mgr


def _status(mgr: SerialManager) -> dict:
    return {
        "type":     "status",
        "state":    "idle" if mgr.is_connected else "disconnected",
        "port":     mgr.port,
        "attached": mgr.attached,
    }


def run_server(host: str = HOST, port: int = PORT):
    app, _, _ = create_app()
    uvicorn.run(app, host=host, port=port, log_level="warning")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s [%(levelname)s] %(message)s")
    detected_port = SerialManager.auto_detect()
    print_banner(detected_port, HOST, PORT)
    run_server(HOST, PORT)
