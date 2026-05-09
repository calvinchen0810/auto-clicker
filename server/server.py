"""
server/server.py
FastAPI + WebSocket 伺服器
"""

import asyncio
import json
import logging
import threading
from pathlib import Path
from typing import Optional

import uvicorn
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, field_validator

from serial_manager import SerialManager

logger = logging.getLogger(__name__)

# index.html 路徑（打包後用 sys._MEIPASS）
def _html_path() -> Path:
    import sys
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).parent))
    return base / "static" / "index.html"


# ─────────────────────────────────────────
#  Pydantic 模型
# ─────────────────────────────────────────

class StepModel(BaseModel):
    delay_ms:    int = Field(0,   ge=0)
    angle:       int = Field(90,  ge=0, le=180)
    speed:       int = Field(60,  ge=1, le=100)
    duration_ms: int = Field(300, ge=0)
    home:        int = Field(1,   ge=0, le=1)

class RunRequest(BaseModel):
    steps: list[StepModel] = Field(..., min_length=1, max_length=48)
    loop:  bool = Field(False)

    @field_validator("steps")
    @classmethod
    def not_empty(cls, v):
        if not v:
            raise ValueError("steps 不能為空")
        return v

class ConnectRequest(BaseModel):
    port: Optional[str] = None


# ─────────────────────────────────────────
#  WebSocket 管理器
# ─────────────────────────────────────────

class WSManager:
    def __init__(self):
        self._clients: list[WebSocket] = []
        self._lock = asyncio.Lock()
        self._loop: asyncio.AbstractEventLoop | None = None

    def set_loop(self, loop: asyncio.AbstractEventLoop):
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
        """Thread-safe broadcast from a non-async serial reader thread."""
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
    app        = FastAPI(title="Servo Controller", version="1.0.0")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"], allow_methods=["*"], allow_headers=["*"],
    )

    # Serial 回調 → WS 廣播
    def on_serial_line(line: str):
        ws_mgr.broadcast_sync({"type": "serial", "line": line})
        # 解析進度
        if line.startswith("OK RUNNING ") and "/" in line:
            try:
                cur, tot = line.split()[-1].split("/")
                # Firmware reports next step index (1-based), so convert to
                # completed-step count for UI progress.
                completed = max(0, int(cur) - 1)
                ws_mgr.broadcast_sync({
                    "type": "status", "state": "running",
                    "step": completed, "total": int(tot),
                    "port": serial_mgr.port,
                })
            except Exception:
                pass
        elif line == "OK DONE":
            ws_mgr.broadcast_sync({"type": "done", "state": "idle"})
        elif line == "OK STOPPED":
            ws_mgr.broadcast_sync({"type": "status", "state": "idle",
                                    "port": serial_mgr.port})
        elif line == "OK READY":
            ws_mgr.broadcast_sync({"type": "status", "state": "idle",
                                    "port": serial_mgr.port})
        elif line.startswith("ERR"):
            ws_mgr.broadcast_sync({"type": "error", "message": line})

    def on_disconnect():
        ws_mgr.broadcast_sync({"type": "status", "state": "disconnected", "port": None})

    serial_mgr.on_line(on_serial_line)
    serial_mgr.on_disconnect(on_disconnect)

    @app.on_event("startup")
    async def _startup():
        ws_mgr.set_loop(asyncio.get_running_loop())

    # ── WebSocket /ws ─────────────────────
    @app.websocket("/ws")
    async def ws_endpoint(ws: WebSocket):
        await ws_mgr.connect(ws)
        # 連線後推送當前狀態
        await ws.send_text(json.dumps(_status(serial_mgr)))
        try:
            while True:
                data = await ws.receive_text()
                msg  = json.loads(data)
                if msg.get("type") == "ping":
                    await ws.send_text(json.dumps({"type": "pong"}))
        except WebSocketDisconnect:
            await ws_mgr.disconnect(ws)

    # ── GET / → index.html ────────────────
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
        ws_mgr.broadcast_sync({"type": "status", "state": "idle", "port": port})
        return {"ok": True, "port": port}

    # ── POST /api/disconnect ──────────────
    @app.post("/api/disconnect")
    async def api_disconnect():
        serial_mgr.disconnect()
        return {"ok": True}

    # ── POST /api/run ─────────────────────
    @app.post("/api/run")
    async def api_run(req: RunRequest):
        if not serial_mgr.is_connected:
            raise HTTPException(400, "尚未連線到 Arduino")
        steps = [s.model_dump() for s in req.steps]
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
        s = req.model_dump()
        ok = await asyncio.get_event_loop().run_in_executor(
            None, lambda: serial_mgr.send_script([s], loop=False)
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

        # Keep browser behavior aligned with serial_tester:
        # a bare STEP command should run as a one-step script.
        if cmd.upper().startswith("STEP "):
            parts = cmd.split()
            if len(parts) not in (5, 6):
                raise HTTPException(400, "STEP 格式錯誤，應為: STEP delay angle speed duration [home]")
            try:
                step = {
                    "delay_ms": int(parts[1]),
                    "angle": int(parts[2]),
                    "speed": int(parts[3]),
                    "duration_ms": int(parts[4]),
                    "home": int(parts[5]) if len(parts) == 6 else 1,
                }
            except ValueError:
                raise HTTPException(400, "STEP 參數必須是數字")

            ok = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: serial_mgr.send_script([step], loop=False)
            )
            if not ok:
                raise HTTPException(500, "STEP 指令傳送失敗")
        else:
            serial_mgr.send(cmd)
        return {"ok": True}

    return app, serial_mgr, ws_mgr


def _status(mgr: SerialManager) -> dict:
    return {
        "type":  "status",
        "state": "idle" if mgr.is_connected else "disconnected",
        "port":  mgr.port,
    }


# ─────────────────────────────────────────
#  啟動入口
# ─────────────────────────────────────────

def run_server(host: str = "127.0.0.1", port: int = 7070):
    app, _, _ = create_app()
    uvicorn.run(app, host=host, port=port, log_level="warning")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s [%(levelname)s] %(message)s")
    run_server()
