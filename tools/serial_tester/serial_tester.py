"""
tools/serial_tester/serial_tester.py

Arduino Servo Serial 測試工具
- 連接真實 Arduino（USB）
- 送出 Serial 指令並查看回應
- 測試單步動作 / 完整腳本 / 緊急停止

執行方式：
    pip install pyserial
    python serial_tester.py
"""

import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
import serial
import serial.tools.list_ports
import threading
import time
from datetime import datetime

# ─────────────────────────────────────────
#  顏色設定
# ─────────────────────────────────────────
BG          = "#0e0e10"
BG_PANEL    = "#161618"
BG_INPUT    = "#1e1e22"
FG          = "#e4e4e7"
FG_DIM      = "#71717a"
GREEN       = "#22c55e"
AMBER       = "#f59e0b"
RED         = "#ef4444"
BLUE        = "#38bdf8"
BORDER      = "#27272a"
FONT_MONO   = ("Consolas", 10)
FONT_UI     = ("Segoe UI", 10)
FONT_UI_B   = ("Segoe UI", 10, "bold")
FONT_TITLE  = ("Segoe UI", 11, "bold")


# ─────────────────────────────────────────
#  Serial 管理
# ─────────────────────────────────────────
class SerialManager:
    def __init__(self, on_line_received):
        self._serial       = None
        self._reader       = None
        self._running      = False
        self._on_line      = on_line_received

    def scan_ports(self):
        ports = []
        for p in serial.tools.list_ports.comports():
            desc   = p.description or ""
            likely = any(k in desc.upper() for k in ["CH340", "CH341", "ARDUINO", "USB SERIAL"])
            ports.append({"port": p.device, "desc": desc, "likely": likely})
        return sorted(ports, key=lambda x: (not x["likely"], x["port"]))

    def connect(self, port, baud=115200) -> bool:
        try:
            self._serial  = serial.Serial(port, baud, timeout=0.1)
            self._running = True
            self._reader  = threading.Thread(target=self._read_loop, daemon=True)
            self._reader.start()
            return True
        except serial.SerialException as e:
            return False

    def disconnect(self):
        self._running = False
        if self._serial and self._serial.is_open:
            self._serial.close()
        self._serial = None

    def send(self, cmd: str):
        if not self._serial or not self._serial.is_open:
            return False
        try:
            self._serial.write((cmd.strip() + "\n").encode())
            return True
        except serial.SerialException:
            return False

    @property
    def is_connected(self):
        return self._serial is not None and self._serial.is_open

    def _read_loop(self):
        while self._running:
            try:
                if not self._serial or not self._serial.is_open:
                    break
                raw = self._serial.readline()
                if raw:
                    line = raw.decode("utf-8", errors="replace").strip()
                    if line:
                        self._on_line(line)
            except serial.SerialException:
                break


# ─────────────────────────────────────────
#  主視窗
# ─────────────────────────────────────────
class SerialTester(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Servo Serial Tester")
        self.geometry("820x680")
        self.configure(bg=BG)
        self.resizable(True, True)

        self._serial = SerialManager(self._on_line_received)
        self._build_ui()
        self._refresh_ports()

    # ── UI 建構 ───────────────────────────

    def _build_ui(self):
        # ── 頂部：連線列 ──────────────────
        top = tk.Frame(self, bg=BG_PANEL, pady=8, padx=12)
        top.pack(fill="x")

        tk.Label(top, text="Servo Serial Tester", bg=BG_PANEL, fg=FG,
                 font=FONT_TITLE).pack(side="left")

        # 狀態燈
        self._dot = tk.Label(top, text="●", bg=BG_PANEL, fg=RED, font=("Consolas", 14))
        self._dot.pack(side="left", padx=(16, 4))
        self._lbl_state = tk.Label(top, text="未連線", bg=BG_PANEL, fg=FG_DIM, font=FONT_UI)
        self._lbl_state.pack(side="left")

        # Port 選擇
        tk.Label(top, text="  Port:", bg=BG_PANEL, fg=FG_DIM, font=FONT_UI).pack(side="left")
        self._port_var = tk.StringVar()
        self._port_cb  = ttk.Combobox(top, textvariable=self._port_var, width=28, font=FONT_MONO, state="readonly")
        self._port_cb.pack(side="left", padx=4)

        self._btn_refresh = tk.Button(top, text="⟳", bg=BG_INPUT, fg=FG_DIM, font=FONT_UI,
                                      bd=0, padx=6, cursor="hand2", command=self._refresh_ports)
        self._btn_refresh.pack(side="left")

        self._btn_conn = tk.Button(top, text="連線", bg="#166534", fg="#bbf7d0",
                                   font=FONT_UI_B, bd=0, padx=12, pady=4,
                                   cursor="hand2", command=self._toggle_connect)
        self._btn_conn.pack(side="left", padx=(8, 0))

        # ── 主體分割：左右 ────────────────
        body = tk.Frame(self, bg=BG)
        body.pack(fill="both", expand=True, padx=10, pady=8)
        body.columnconfigure(0, weight=1)
        body.columnconfigure(1, weight=1)
        body.rowconfigure(0, weight=1)

        # 左欄
        left = tk.Frame(body, bg=BG)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 5))
        self._build_left(left)

        # 右欄：Serial Log
        right = tk.Frame(body, bg=BG)
        right.grid(row=0, column=1, sticky="nsew", padx=(5, 0))
        self._build_log(right)

    def _build_left(self, parent):
        parent.rowconfigure(0, weight=0)
        parent.rowconfigure(1, weight=0)
        parent.rowconfigure(2, weight=1)
        parent.columnconfigure(0, weight=1)

        # ── 快速指令 ──────────────────────
        grp1 = self._group(parent, "快速指令")
        grp1.grid(row=0, column=0, sticky="ew", pady=(0, 6))

        btns = [
            ("PING",   BLUE,  lambda: self._send("PING")),
            ("STATUS", AMBER, lambda: self._send("STATUS")),
            ("STOP",   RED,   lambda: self._send("STOP")),
        ]
        row = tk.Frame(grp1, bg=BG_PANEL)
        row.pack(fill="x", padx=8, pady=8)
        for text, color, cmd in btns:
            b = tk.Button(row, text=text, bg=BG_INPUT, fg=color, font=FONT_UI_B,
                          bd=0, padx=14, pady=6, cursor="hand2", command=cmd)
            b.pack(side="left", padx=4)

        # ── 單步測試 ──────────────────────
        grp2 = self._group(parent, "單步測試")
        grp2.grid(row=1, column=0, sticky="ew", pady=(0, 6))

        fields = tk.Frame(grp2, bg=BG_PANEL)
        fields.pack(fill="x", padx=8, pady=(6, 0))

        self._delay_var    = tk.IntVar(value=0)
        self._angle_var    = tk.IntVar(value=90)
        self._speed_var    = tk.IntVar(value=60)
        self._duration_var = tk.IntVar(value=300)

        specs = [
            ("延遲 ms",  self._delay_var,    0,     65535),
            ("角度 °",   self._angle_var,    0,     180),
            ("速度",     self._speed_var,    1,     100),
            ("停留 ms",  self._duration_var, 0,     65535),
        ]
        for i, (label, var, lo, hi) in enumerate(specs):
            col = (i % 2) * 2
            r   = i // 2
            tk.Label(fields, text=label, bg=BG_PANEL, fg=FG_DIM,
                     font=FONT_UI).grid(row=r, column=col, sticky="w", padx=(4, 2), pady=3)
            sb = tk.Spinbox(fields, from_=lo, to=hi, textvariable=var, width=8,
                            bg=BG_INPUT, fg=FG, font=FONT_MONO,
                            buttonbackground=BG_INPUT, relief="flat", bd=1)
            sb.grid(row=r, column=col+1, sticky="ew", padx=(0, 12), pady=3)
        fields.columnconfigure(1, weight=1)
        fields.columnconfigure(3, weight=1)

        # Servo 角度視覺指示器
        self._canvas = tk.Canvas(grp2, width=100, height=100, bg=BG_PANEL, highlightthickness=0)
        self._canvas.pack(pady=4)
        self._draw_servo_indicator(0)

        btn_row = tk.Frame(grp2, bg=BG_PANEL)
        btn_row.pack(fill="x", padx=8, pady=8)
        tk.Button(btn_row, text="▶  送出單步", bg="#14532d", fg="#bbf7d0",
                  font=FONT_UI_B, bd=0, padx=14, pady=6, cursor="hand2",
                  command=self._send_step).pack(side="left")
        tk.Button(btn_row, text="預覽指令", bg=BG_INPUT, fg=FG_DIM,
                  font=FONT_UI, bd=0, padx=10, pady=6, cursor="hand2",
                  command=self._preview_step).pack(side="left", padx=8)

        # ── 腳本測試 ──────────────────────
        grp3 = self._group(parent, "腳本測試")
        grp3.grid(row=2, column=0, sticky="nsew")

        script_btns = tk.Frame(grp3, bg=BG_PANEL)
        script_btns.pack(fill="x", padx=8, pady=6)

        self._loop_var = tk.BooleanVar(value=False)
        tk.Checkbutton(script_btns, text="循環", variable=self._loop_var,
                       bg=BG_PANEL, fg=FG, selectcolor=BG_INPUT,
                       activebackground=BG_PANEL, font=FONT_UI).pack(side="left")

        tk.Button(script_btns, text="載入範例", bg=BG_INPUT, fg=FG_DIM,
                  font=FONT_UI, bd=0, padx=10, pady=4, cursor="hand2",
                  command=self._load_example).pack(side="left", padx=6)
        tk.Button(script_btns, text="▶ 執行腳本", bg="#14532d", fg="#bbf7d0",
                  font=FONT_UI_B, bd=0, padx=12, pady=4, cursor="hand2",
                  command=self._run_script).pack(side="left", padx=4)
        tk.Button(script_btns, text="■ STOP", bg="#7f1d1d", fg="#fca5a5",
                  font=FONT_UI_B, bd=0, padx=10, pady=4, cursor="hand2",
                  command=lambda: self._send("STOP")).pack(side="left", padx=4)

        # 腳本文字區
        self._script_text = tk.Text(grp3, bg=BG_INPUT, fg=FG, font=FONT_MONO,
                                    insertbackground=FG, relief="flat",
                                    bd=0, padx=6, pady=6)
        self._script_text.pack(fill="both", expand=True, padx=8, pady=(0, 8))

        self._load_example()  # 預載範例

    def _build_log(self, parent):
        grp = self._group(parent, "Serial Log")
        grp.pack(fill="both", expand=True)

        # 工具列
        log_top = tk.Frame(grp, bg=BG_PANEL)
        log_top.pack(fill="x", padx=8, pady=(4, 0))

        tk.Button(log_top, text="清除", bg=BG_INPUT, fg=FG_DIM,
                  font=FONT_UI, bd=0, padx=8, pady=2,
                  cursor="hand2", command=self._clear_log).pack(side="right")
        self._lbl_count = tk.Label(log_top, text="0 行", bg=BG_PANEL, fg=FG_DIM, font=FONT_UI)
        self._lbl_count.pack(side="right", padx=8)

        # 輸出區
        self._log = scrolledtext.ScrolledText(
            grp, bg=BG, fg=GREEN, font=FONT_MONO,
            insertbackground=FG, relief="flat", bd=0,
            padx=6, pady=6, state="disabled"
        )
        self._log.pack(fill="both", expand=True, padx=8, pady=4)

        # 顏色 tag
        self._log.tag_config("ok_ready",   foreground=GREEN)
        self._log.tag_config("ok_running", foreground=AMBER)
        self._log.tag_config("ok_done",    foreground=GREEN)
        self._log.tag_config("ok_other",   foreground="#a3e635")
        self._log.tag_config("err",        foreground=RED)
        self._log.tag_config("send",       foreground=BLUE)
        self._log.tag_config("ts",         foreground=FG_DIM)
        self._log.tag_config("info",       foreground=FG_DIM)

        # 手動輸入列
        input_row = tk.Frame(grp, bg=BG_PANEL)
        input_row.pack(fill="x", padx=8, pady=(0, 8))

        tk.Label(input_row, text=">>", bg=BG_PANEL, fg=BLUE, font=FONT_MONO).pack(side="left")
        self._cmd_var = tk.StringVar()
        self._cmd_entry = tk.Entry(input_row, textvariable=self._cmd_var,
                                   bg=BG_INPUT, fg=FG, font=FONT_MONO,
                                   insertbackground=FG, relief="flat", bd=0)
        self._cmd_entry.pack(side="left", fill="x", expand=True, padx=(4, 6))
        self._cmd_entry.bind("<Return>", lambda e: self._send_manual())

        tk.Button(input_row, text="送出", bg=BG_INPUT, fg=FG,
                  font=FONT_UI, bd=0, padx=10, pady=3,
                  cursor="hand2", command=self._send_manual).pack(side="left")

    def _group(self, parent, title):
        frame = tk.LabelFrame(parent, text=f"  {title}  ", bg=BG_PANEL, fg=AMBER,
                              font=("Consolas", 9), bd=1, relief="groove",
                              highlightbackground=BORDER)
        return frame

    # ── Servo 角度視覺指示器 ──────────────

    def _draw_servo_indicator(self, angle: int):
        import math
        c = self._canvas
        c.delete("all")
        cx, cy, r = 50, 60, 36

        # 背景圓弧（0–180°）
        c.create_arc(cx-r, cy-r, cx+r, cy+r, start=0, extent=180,
                     style="arc", outline=BORDER, width=2)

        # 角度指針
        rad = math.radians(180 - angle)
        ex  = cx + r * math.cos(rad)
        ey  = cy - r * math.sin(rad)
        c.create_line(cx, cy, ex, ey, fill=GREEN, width=2)
        c.create_oval(cx-4, cy-4, cx+4, cy+4, fill=AMBER, outline="")

        # 角度文字
        c.create_text(cx, cy+22, text=f"{angle}°", fill=FG, font=FONT_MONO)

    # ── 連線控制 ─────────────────────────

    def _refresh_ports(self):
        ports = self._serial.scan_ports()
        items = []
        for p in ports:
            prefix = "⭐ " if p["likely"] else "   "
            items.append(f"{prefix}{p['port']}  {p['desc']}")
        self._port_cb["values"] = items
        if items:
            self._port_cb.current(0)

    def _get_selected_port(self):
        val = self._port_var.get().strip()
        for part in val.split():
            if part.startswith("COM") or part.startswith("/dev/"):
                return part
        return None

    def _toggle_connect(self):
        if self._serial.is_connected:
            self._serial.disconnect()
            self._set_connected(False)
            self._log_info("已中斷連線")
        else:
            port = self._get_selected_port()
            if not port:
                messagebox.showerror("錯誤", "請先選擇 COM port")
                return
            ok = self._serial.connect(port)
            if ok:
                self._set_connected(True)
                self._log_info(f"已連線到 {port}（鮑率 115200）")
            else:
                messagebox.showerror("連線失敗", f"無法開啟 {port}\n請確認 Arduino 已插入且驅動已安裝")

    def _set_connected(self, connected: bool):
        if connected:
            self._dot.config(fg=GREEN)
            self._lbl_state.config(text=f"已連線  {self._get_selected_port()}", fg=GREEN)
            self._btn_conn.config(text="斷線", bg="#7f1d1d", fg="#fca5a5")
        else:
            self._dot.config(fg=RED)
            self._lbl_state.config(text="未連線", fg=FG_DIM)
            self._btn_conn.config(text="連線", bg="#166534", fg="#bbf7d0")

    # ── 指令發送 ─────────────────────────

    def _send(self, cmd: str):
        if not self._serial.is_connected:
            self._log_info("⚠  未連線")
            return False
        self._log_send(cmd)
        return self._serial.send(cmd)

    def _send_manual(self):
        cmd = self._cmd_var.get().strip()
        if cmd:
            self._send(cmd)
            self._cmd_var.set("")

    def _send_step(self):
        d   = self._delay_var.get()
        a   = self._angle_var.get()
        sp  = self._speed_var.get()
        dur = self._duration_var.get()

        # 更新角度指示器
        self._draw_servo_indicator(a)

        # 送出腳本（按下 + 放開）
        self._send(f"LOOP 0")
        time.sleep(0.05)
        self._send("BEGIN 2")
        time.sleep(0.05)
        self._send(f"STEP {d} {a} {sp} {dur}")
        time.sleep(0.05)
        self._send(f"STEP 0 0 {sp} 0")
        time.sleep(0.05)
        self._send("END")

    def _preview_step(self):
        d   = self._delay_var.get()
        a   = self._angle_var.get()
        sp  = self._speed_var.get()
        dur = self._duration_var.get()
        self._draw_servo_indicator(a)
        self._log_info(f"預覽: LOOP 0 | BEGIN 2 | STEP {d} {a} {sp} {dur} | STEP 0 0 {sp} 0 | END")

    def _load_example(self):
        example = (
            "# 10秒後按3次，每次間隔3秒\n"
            "# 修改後點「執行腳本」\n"
            "LOOP 0\n"
            "BEGIN 6\n"
            "STEP 10000 90 60 300\n"
            "STEP 0 0 60 0\n"
            "STEP 3000 90 60 300\n"
            "STEP 0 0 60 0\n"
            "STEP 3000 90 60 300\n"
            "STEP 0 0 60 0\n"
            "END\n"
        )
        self._script_text.delete("1.0", "end")
        self._script_text.insert("1.0", example)

    def _run_script(self):
        if not self._serial.is_connected:
            self._log_info("⚠  未連線")
            return

        raw_lines = self._script_text.get("1.0", "end").splitlines()
        # 過濾空行和註解
        lines = [l.strip() for l in raw_lines if l.strip() and not l.strip().startswith("#")]

        if not lines:
            messagebox.showwarning("腳本為空", "請輸入腳本內容")
            return

        # 如果勾選循環，覆蓋第一行 LOOP
        if self._loop_var.get():
            lines = [l for l in lines if not l.startswith("LOOP")]
            lines.insert(0, "LOOP 1")

        def send_all():
            for line in lines:
                self._send(line)
                time.sleep(0.06)

        threading.Thread(target=send_all, daemon=True).start()

    # ── Serial Log ───────────────────────

    def _on_line_received(self, line: str):
        """從 reader thread 呼叫，需切換到主執行緒"""
        self.after(0, lambda: self._log_rx(line))

    def _log_rx(self, line: str):
        tag = "ok_other"
        if line in ("OK READY", "OK DONE", "OK PONG", "OK IDLE", "OK STOPPED"):
            tag = "ok_ready"
        elif line.startswith("OK RUNNING") or line.startswith("OK LOOP"):
            tag = "ok_running"
        elif line.startswith("ERR"):
            tag = "err"

        self._append_log(f"← {line}", tag)

    def _log_send(self, cmd: str):
        self._append_log(f"→ {cmd}", "send")

    def _log_info(self, msg: str):
        self._append_log(f"   {msg}", "info")

    def _append_log(self, text: str, tag: str):
        ts  = datetime.now().strftime("%H:%M:%S")
        self._log.config(state="normal")
        self._log.insert("end", f"{ts}  ", "ts")
        self._log.insert("end", text + "\n", tag)
        self._log.see("end")
        self._log.config(state="disabled")

        # 更新行數
        lines = int(self._log.index("end-1c").split(".")[0])
        self._lbl_count.config(text=f"{lines} 行")

    def _clear_log(self):
        self._log.config(state="normal")
        self._log.delete("1.0", "end")
        self._log.config(state="disabled")
        self._lbl_count.config(text="0 行")

    # ── 關閉 ─────────────────────────────

    def on_close(self):
        self._serial.disconnect()
        self.destroy()


# ─────────────────────────────────────────
#  Entry Point
# ─────────────────────────────────────────
if __name__ == "__main__":
    app = SerialTester()
    app.protocol("WM_DELETE_WINDOW", app.on_close)

    # 設定深色標題列（Windows 11）
    try:
        import ctypes
        HWND = ctypes.windll.user32.GetParent(app.winfo_id())
        ctypes.windll.dwmapi.DwmSetWindowAttribute(HWND, 20, ctypes.byref(ctypes.c_int(1)), 4)
    except Exception:
        pass

    app.mainloop()
