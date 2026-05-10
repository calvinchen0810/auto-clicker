"""
tools/serial_tester/serial_tester.py

Arduino Servo Serial 測試工具（多 Servo 支援）
- 最多 6 顆 SG90 Servo
- 動態 ATTACH / DETACH
- 單步測試 / 腳本測試 / Serial Monitor

STEP 格式：delay_ms servo_id angle speed duration_ms [home]
  home=1（預設）→ 執行完回到 0°
  home=0        → 停在目標角度

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

BG         = "#0e0e10"
BG_PANEL   = "#161618"
BG_INPUT   = "#1e1e22"
FG         = "#e4e4e7"
FG_DIM     = "#71717a"
GREEN      = "#22c55e"
AMBER      = "#f59e0b"
RED        = "#ef4444"
BLUE       = "#38bdf8"
BORDER     = "#27272a"
FONT_MONO  = ("Consolas", 10)
FONT_UI    = ("Segoe UI", 10)
FONT_UI_B  = ("Segoe UI", 10, "bold")
FONT_TITLE = ("Segoe UI", 11, "bold")

MAX_SERVOS = 6
PWM_PINS   = [9, 10, 11, 6, 5, 3]


class SerialManager:
    def __init__(self, on_line_received):
        self._serial  = None
        self._reader  = None
        self._running = False
        self._on_line = on_line_received

    def scan_ports(self):
        ports = []
        for p in serial.tools.list_ports.comports():
            desc   = p.description or ""
            likely = any(k in desc.upper() for k in ["CH340","CH341","ARDUINO","USB SERIAL"])
            ports.append({"port": p.device, "desc": desc, "likely": likely})
        return sorted(ports, key=lambda x: (not x["likely"], x["port"]))

    def connect(self, port, baud=115200) -> bool:
        try:
            self._serial  = serial.Serial(port, baud, timeout=0.1)
            self._running = True
            self._reader  = threading.Thread(target=self._read_loop, daemon=True)
            self._reader.start()
            return True
        except serial.SerialException:
            return False

    def disconnect(self):
        self._running = False
        if self._serial and self._serial.is_open:
            self._serial.close()
        self._serial = None

    def send(self, cmd: str) -> bool:
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


class SerialTester(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Servo Serial Tester")
        self.geometry("1100x780")
        self.configure(bg=BG)
        self.resizable(True, True)

        self._serial     = SerialManager(self._on_line_received)
        self._attached   = [False] * MAX_SERVOS
        self._pin_vars   = [tk.IntVar(value=PWM_PINS[i]) for i in range(MAX_SERVOS)]
        self._servo_rows = []

        self._build_ui()
        self._refresh_ports()

    def _build_ui(self):
        top = tk.Frame(self, bg=BG_PANEL, pady=8, padx=12)
        top.pack(fill="x")
        tk.Label(top, text="Servo Serial Tester", bg=BG_PANEL, fg=FG, font=FONT_TITLE).pack(side="left")
        self._dot = tk.Label(top, text="●", bg=BG_PANEL, fg=RED, font=("Consolas",14))
        self._dot.pack(side="left", padx=(16,4))
        self._lbl_state = tk.Label(top, text="未連線", bg=BG_PANEL, fg=FG_DIM, font=FONT_UI)
        self._lbl_state.pack(side="left")
        tk.Label(top, text="  Port:", bg=BG_PANEL, fg=FG_DIM, font=FONT_UI).pack(side="left")
        self._port_var = tk.StringVar()
        self._port_cb  = ttk.Combobox(top, textvariable=self._port_var, width=28, font=FONT_MONO, state="readonly")
        self._port_cb.pack(side="left", padx=4)
        tk.Button(top, text="⟳", bg=BG_INPUT, fg=FG_DIM, font=FONT_UI, bd=0, padx=6, cursor="hand2", command=self._refresh_ports).pack(side="left")
        self._btn_conn = tk.Button(top, text="連線", bg="#166534", fg="#bbf7d0", font=FONT_UI_B, bd=0, padx=12, pady=4, cursor="hand2", command=self._toggle_connect)
        self._btn_conn.pack(side="left", padx=(8,0))

        body = tk.Frame(self, bg=BG)
        body.pack(fill="both", expand=True, padx=10, pady=8)
        body.columnconfigure(0, weight=0, minsize=260)
        body.columnconfigure(1, weight=1)
        body.columnconfigure(2, weight=1)
        body.rowconfigure(0, weight=1)

        left = tk.Frame(body, bg=BG)
        left.grid(row=0, column=0, sticky="nsew", padx=(0,5))
        self._build_servo_manager(left)

        mid = tk.Frame(body, bg=BG)
        mid.grid(row=0, column=1, sticky="nsew", padx=(0,5))
        self._build_mid(mid)

        right = tk.Frame(body, bg=BG)
        right.grid(row=0, column=2, sticky="nsew")
        self._build_log(right)

    def _build_servo_manager(self, parent):
        parent.rowconfigure(0, weight=0)
        parent.rowconfigure(1, weight=0)
        parent.columnconfigure(0, weight=1)

        grp = self._group(parent, "Servo 管理（ATTACH / DETACH）")
        grp.grid(row=0, column=0, sticky="ew", pady=(0,6))

        hdr = tk.Frame(grp, bg=BG_PANEL)
        hdr.pack(fill="x", padx=8, pady=(6,2))
        for text, w in [("ID",28),("腳位",52),("狀態",70),("操作",100)]:
            tk.Label(hdr, text=text, bg=BG_PANEL, fg=FG_DIM, font=("Consolas",9), width=w//8, anchor="w").pack(side="left", padx=2)

        self._servo_rows = []
        for i in range(MAX_SERVOS):
            self._servo_rows.append(self._build_servo_row(grp, i))

        bulk = tk.Frame(grp, bg=BG_PANEL)
        bulk.pack(fill="x", padx=8, pady=(4,8))
        tk.Button(bulk, text="全部 ATTACH", bg=BG_INPUT, fg=GREEN, font=FONT_UI, bd=0, padx=8, pady=3, cursor="hand2", command=self._attach_all).pack(side="left", padx=(0,6))
        tk.Button(bulk, text="全部 DETACH", bg=BG_INPUT, fg=RED,   font=FONT_UI, bd=0, padx=8, pady=3, cursor="hand2", command=self._detach_all).pack(side="left")

        grp2 = self._group(parent, "快速指令")
        grp2.grid(row=1, column=0, sticky="ew", pady=(0,6))
        qrow = tk.Frame(grp2, bg=BG_PANEL)
        qrow.pack(fill="x", padx=8, pady=8)
        for text, color, cmd in [
            ("PING",   BLUE,  lambda: self._send("PING")),
            ("STATUS", AMBER, lambda: self._send("STATUS")),
            ("STOP",   RED,   lambda: self._send("STOP")),
        ]:
            tk.Button(qrow, text=text, bg=BG_INPUT, fg=color, font=FONT_UI_B, bd=0, padx=10, pady=5, cursor="hand2", command=cmd).pack(side="left", padx=3)

    def _build_servo_row(self, parent, i):
        sid = i + 1
        f = tk.Frame(parent, bg=BG_PANEL)
        f.pack(fill="x", padx=8, pady=1)
        tk.Label(f, text=f"S{sid}", bg=BG_PANEL, fg=FG_DIM, font=FONT_MONO, width=3).pack(side="left", padx=(0,4))
        pin_sb = tk.Spinbox(f, from_=2, to=13, textvariable=self._pin_vars[i], width=4, bg=BG_INPUT, fg=FG, font=FONT_MONO, buttonbackground=BG_INPUT, relief="flat", bd=1)
        pin_sb.pack(side="left", padx=(0,4))
        dot = tk.Label(f, text="●", fg=FG_DIM, bg=BG_PANEL, font=("Consolas",12))
        dot.pack(side="left", padx=(0,4))
        lbl = tk.Label(f, text="—", fg=FG_DIM, bg=BG_PANEL, font=FONT_MONO, width=8, anchor="w")
        lbl.pack(side="left", padx=(0,4))
        btn_a = tk.Button(f, text="ATTACH", bg=BG_INPUT, fg=GREEN, font=FONT_UI, bd=0, padx=6, pady=2, cursor="hand2", command=lambda s=sid,pi=i: self._attach_servo(s,pi))
        btn_a.pack(side="left", padx=(0,3))
        btn_d = tk.Button(f, text="DETACH", bg=BG_INPUT, fg=FG_DIM, font=FONT_UI, bd=0, padx=6, pady=2, cursor="hand2", state="disabled", command=lambda s=sid,pi=i: self._detach_servo(s,pi))
        btn_d.pack(side="left")
        return {"dot":dot,"lbl":lbl,"btn_attach":btn_a,"btn_detach":btn_d,"pin_sb":pin_sb}

    def _build_mid(self, parent):
        parent.rowconfigure(0, weight=0)
        parent.rowconfigure(1, weight=1)
        parent.columnconfigure(0, weight=1)

        grp1 = self._group(parent, "單步測試")
        grp1.grid(row=0, column=0, sticky="ew", pady=(0,6))

        fields = tk.Frame(grp1, bg=BG_PANEL)
        fields.pack(fill="x", padx=8, pady=(8,0))
        self._delay_var    = tk.IntVar(value=0)
        self._sid_var      = tk.IntVar(value=1)
        self._angle_var    = tk.IntVar(value=90)
        self._speed_var    = tk.IntVar(value=60)
        self._duration_var = tk.IntVar(value=300)
        self._home_var     = tk.IntVar(value=1)

        for i,(label,var,lo,hi) in enumerate([
            ("延遲 ms",  self._delay_var,    0, 65535),
            ("Servo ID", self._sid_var,      1, 6),
            ("角度 °",   self._angle_var,    0, 180),
            ("速度",     self._speed_var,    1, 100),
            ("停留 ms",  self._duration_var, 0, 65535),
        ]):
            col = (i%2)*2; r = i//2
            tk.Label(fields, text=label, bg=BG_PANEL, fg=FG_DIM, font=FONT_UI).grid(row=r, column=col, sticky="w", padx=(4,2), pady=3)
            sb = tk.Spinbox(fields, from_=lo, to=hi, textvariable=var, width=8, bg=BG_INPUT, fg=AMBER if label=="Servo ID" else FG, font=FONT_MONO, buttonbackground=BG_INPUT, relief="flat", bd=1)
            sb.grid(row=r, column=col+1, sticky="ew", padx=(0,12), pady=3)
        fields.columnconfigure(1, weight=1); fields.columnconfigure(3, weight=1)

        home_row = tk.Frame(grp1, bg=BG_PANEL)
        home_row.pack(fill="x", padx=8, pady=(4,0))
        tk.Label(home_row, text="歸位", bg=BG_PANEL, fg=FG_DIM, font=FONT_UI).pack(side="left", padx=(4,8))
        self._btn_home1 = tk.Button(home_row, text="1  回 0°", font=FONT_UI, bg="#14532d", fg="#bbf7d0", bd=0, padx=10, pady=3, cursor="hand2", command=lambda: self._set_home(1))
        self._btn_home1.pack(side="left", padx=(0,4))
        self._btn_home0 = tk.Button(home_row, text="0  停住",  font=FONT_UI, bg=BG_INPUT, fg=FG_DIM, bd=0, padx=10, pady=3, cursor="hand2", command=lambda: self._set_home(0))
        self._btn_home0.pack(side="left")

        ind = tk.Frame(grp1, bg=BG_PANEL)
        ind.pack(fill="x", padx=8, pady=4)
        self._canvas = tk.Canvas(ind, width=110, height=80, bg=BG_PANEL, highlightthickness=0)
        self._canvas.pack(side="left")
        self._draw_servo_indicator(0, home=1)
        self._lbl_home_desc = tk.Label(ind, text="home=1\n執行完\n回到 0°", bg=BG_PANEL, fg=GREEN, font=("Consolas",9), justify="left")
        self._lbl_home_desc.pack(side="left", padx=12)

        btn_row = tk.Frame(grp1, bg=BG_PANEL)
        btn_row.pack(fill="x", padx=8, pady=8)
        tk.Button(btn_row, text="▶  送出單步", bg="#14532d", fg="#bbf7d0", font=FONT_UI_B, bd=0, padx=14, pady=5, cursor="hand2", command=self._send_step).pack(side="left")
        tk.Button(btn_row, text="預覽指令", bg=BG_INPUT, fg=FG_DIM, font=FONT_UI, bd=0, padx=10, pady=5, cursor="hand2", command=self._preview_step).pack(side="left", padx=8)

        grp2 = self._group(parent, "腳本測試")
        grp2.grid(row=1, column=0, sticky="nsew")
        sb2 = tk.Frame(grp2, bg=BG_PANEL)
        sb2.pack(fill="x", padx=8, pady=6)
        self._loop_var = tk.BooleanVar(value=False)
        tk.Checkbutton(sb2, text="循環", variable=self._loop_var, bg=BG_PANEL, fg=FG, selectcolor=BG_INPUT, activebackground=BG_PANEL, font=FONT_UI).pack(side="left")
        tk.Button(sb2, text="載入範例", bg=BG_INPUT, fg=FG_DIM, font=FONT_UI, bd=0, padx=10, pady=3, cursor="hand2", command=self._load_example).pack(side="left", padx=6)
        tk.Button(sb2, text="▶ 執行腳本", bg="#14532d", fg="#bbf7d0", font=FONT_UI_B, bd=0, padx=12, pady=3, cursor="hand2", command=self._run_script).pack(side="left", padx=4)
        tk.Button(sb2, text="■ STOP", bg="#7f1d1d", fg="#fca5a5", font=FONT_UI_B, bd=0, padx=10, pady=3, cursor="hand2", command=lambda: self._send("STOP")).pack(side="left", padx=4)
        self._script_text = tk.Text(grp2, bg=BG_INPUT, fg=FG, font=FONT_MONO, insertbackground=FG, relief="flat", bd=0, padx=6, pady=6)
        self._script_text.pack(fill="both", expand=True, padx=8, pady=(0,8))
        self._load_example()

    def _build_log(self, parent):
        grp = self._group(parent, "Serial Log")
        grp.pack(fill="both", expand=True)
        lt = tk.Frame(grp, bg=BG_PANEL)
        lt.pack(fill="x", padx=8, pady=(4,0))
        tk.Button(lt, text="清除", bg=BG_INPUT, fg=FG_DIM, font=FONT_UI, bd=0, padx=8, pady=2, cursor="hand2", command=self._clear_log).pack(side="right")
        self._lbl_count = tk.Label(lt, text="0 行", bg=BG_PANEL, fg=FG_DIM, font=FONT_UI)
        self._lbl_count.pack(side="right", padx=8)
        self._log = scrolledtext.ScrolledText(grp, bg=BG, fg=GREEN, font=FONT_MONO, insertbackground=FG, relief="flat", bd=0, padx=6, pady=6, state="disabled")
        self._log.pack(fill="both", expand=True, padx=8, pady=4)
        for tag, color in [("ok_ready",GREEN),("ok_running",AMBER),("ok_other","#a3e635"),("err",RED),("send",BLUE),("ts",FG_DIM),("info",FG_DIM)]:
            self._log.tag_config(tag, foreground=color)
        ir = tk.Frame(grp, bg=BG_PANEL)
        ir.pack(fill="x", padx=8, pady=(0,8))
        tk.Label(ir, text=">>", bg=BG_PANEL, fg=BLUE, font=FONT_MONO).pack(side="left")
        self._cmd_var = tk.StringVar()
        self._cmd_entry = tk.Entry(ir, textvariable=self._cmd_var, bg=BG_INPUT, fg=FG, font=FONT_MONO, insertbackground=FG, relief="flat", bd=0)
        self._cmd_entry.pack(side="left", fill="x", expand=True, padx=(4,6))
        self._cmd_entry.bind("<Return>", lambda e: self._send_manual())
        tk.Button(ir, text="送出", bg=BG_INPUT, fg=FG, font=FONT_UI, bd=0, padx=10, pady=3, cursor="hand2", command=self._send_manual).pack(side="left")

    def _group(self, parent, title):
        return tk.LabelFrame(parent, text=f"  {title}  ", bg=BG_PANEL, fg=AMBER, font=("Consolas",9), bd=1, relief="groove", highlightbackground=BORDER)

    # ── Servo 管理 ────────────────────────

    def _attach_servo(self, sid, idx):
        if not self._serial.is_connected:
            self._log_info("⚠  未連線"); return
        pin = self._pin_vars[idx].get()
        self._send(f"ATTACH {sid} {pin}")
        self._attached[idx] = True
        self._update_servo_row(idx)

    def _detach_servo(self, sid, idx):
        if not self._serial.is_connected:
            self._log_info("⚠  未連線"); return
        self._send(f"DETACH {sid}")
        self._attached[idx] = False
        self._update_servo_row(idx)

    def _attach_all(self):
        def go():
            for i in range(MAX_SERVOS):
                self._attach_servo(i+1, i); time.sleep(0.15)
        threading.Thread(target=go, daemon=True).start()

    def _detach_all(self):
        def go():
            for i in range(MAX_SERVOS):
                if self._attached[i]:
                    self._detach_servo(i+1, i); time.sleep(0.1)
        threading.Thread(target=go, daemon=True).start()

    def _update_servo_row(self, idx):
        row    = self._servo_rows[idx]
        is_att = self._attached[idx]
        pin    = self._pin_vars[idx].get()
        row["dot"].config(fg=GREEN if is_att else FG_DIM)
        row["lbl"].config(text=f"D{pin} ✓" if is_att else "—", fg=GREEN if is_att else FG_DIM)
        row["btn_attach"].config(bg="#14532d" if not is_att else BG_INPUT, fg=GREEN if not is_att else FG_DIM, state="normal" if not is_att else "disabled")
        row["btn_detach"].config(bg="#7f1d1d" if is_att else BG_INPUT, fg="#fca5a5" if is_att else FG_DIM, state="normal" if is_att else "disabled")
        row["pin_sb"].config(state="disabled" if is_att else "normal")

    def _parse_status_attached(self, line):
        try:
            part = line.split("ATTACHED=")[1].strip()
            ids  = [] if part=="0" else [int(x) for x in part.split(",") if x.strip().isdigit()]
            for i in range(MAX_SERVOS):
                self._attached[i] = (i+1) in ids
                self._update_servo_row(i)
        except Exception:
            pass

    # ── home / canvas ─────────────────────

    def _set_home(self, val):
        self._home_var.set(val)
        if val == 1:
            self._btn_home1.config(bg="#14532d", fg="#bbf7d0")
            self._btn_home0.config(bg=BG_INPUT,  fg=FG_DIM)
            self._lbl_home_desc.config(text="home=1\n執行完\n回到 0°", fg=GREEN)
        else:
            self._btn_home1.config(bg=BG_INPUT,  fg=FG_DIM)
            self._btn_home0.config(bg="#78350f",  fg="#fde68a")
            self._lbl_home_desc.config(text="home=0\n停在\n目標角度", fg=AMBER)
        self._draw_servo_indicator(self._angle_var.get(), home=val)

    def _draw_servo_indicator(self, angle, home=None):
        import math
        if home is None: home = self._home_var.get()
        c = self._canvas; c.delete("all")
        cx, cy, r = 55, 55, 38
        c.create_arc(cx-r,cy-r,cx+r,cy+r, start=0, extent=180, style="arc", outline=BORDER, width=2)
        if home==1 and angle>0:
            c.create_arc(cx-r+6,cy-r+6,cx+r-6,cy+r-6, start=0, extent=angle, style="arc", outline="#1a4a1a", width=1, dash=(3,3))
        rad = math.radians(angle)
        ex = cx+r*math.cos(rad); ey = cy-r*math.sin(rad)
        color = GREEN if home==1 else AMBER
        c.create_line(cx,cy,ex,ey, fill=color, width=2.5)
        c.create_oval(cx-4,cy-4,cx+4,cy+4, fill=AMBER, outline="")
        if home==1:
            c.create_oval(cx+r-4,cy-4,cx+r+4,cy+4, fill="#1a4a1a", outline=GREEN, width=1)
        c.create_text(cx, cy+20, text=f"{angle}°", fill=FG, font=FONT_MONO)

    # ── 連線 ──────────────────────────────

    def _refresh_ports(self):
        ports = self._serial.scan_ports()
        items = [f"{'⭐ ' if p['likely'] else '   '}{p['port']}  {p['desc']}" for p in ports]
        self._port_cb["values"] = items
        if items: self._port_cb.current(0)

    def _get_selected_port(self):
        val = self._port_var.get().strip()
        for part in val.split():
            if part.startswith("COM") or part.startswith("/dev/"): return part
        return None

    def _toggle_connect(self):
        if self._serial.is_connected:
            self._serial.disconnect()
            self._set_connected(False)
            for i in range(MAX_SERVOS):
                self._attached[i] = False; self._update_servo_row(i)
            self._log_info("已中斷連線")
        else:
            port = self._get_selected_port()
            if not port: messagebox.showerror("錯誤","請先選擇 COM port"); return
            if self._serial.connect(port):
                self._set_connected(True)
                self._log_info(f"已連線到 {port}（鮑率 115200）")
                time.sleep(0.2); self._send("STATUS")
            else:
                messagebox.showerror("連線失敗", f"無法開啟 {port}\n請確認 Arduino 已插入且驅動已安裝")

    def _set_connected(self, connected):
        if connected:
            self._dot.config(fg=GREEN)
            self._lbl_state.config(text=f"已連線  {self._get_selected_port()}", fg=GREEN)
            self._btn_conn.config(text="斷線", bg="#7f1d1d", fg="#fca5a5")
        else:
            self._dot.config(fg=RED)
            self._lbl_state.config(text="未連線", fg=FG_DIM)
            self._btn_conn.config(text="連線", bg="#166534", fg="#bbf7d0")

    # ── 指令 ──────────────────────────────

    def _send(self, cmd):
        if not self._serial.is_connected: self._log_info("⚠  未連線"); return False
        self._log_send(cmd); return self._serial.send(cmd)

    def _send_manual(self):
        cmd = self._cmd_var.get().strip()
        if cmd: self._send(cmd); self._cmd_var.set("")

    def _build_step_cmd(self):
        return (f"STEP {self._delay_var.get()} {self._sid_var.get()} "
                f"{self._angle_var.get()} {self._speed_var.get()} "
                f"{self._duration_var.get()} {self._home_var.get()}")

    def _send_step(self):
        sid = self._sid_var.get(); idx = sid - 1
        a = self._angle_var.get(); h = self._home_var.get()
        if not self._attached[idx]:
            if not messagebox.askyesno("Servo 未 ATTACH",
                    f"Servo {sid} 尚未 ATTACH，是否先以 D{self._pin_vars[idx].get()} 進行 ATTACH？"):
                return
            self._attach_servo(sid, idx); time.sleep(0.4)
        self._draw_servo_indicator(a, home=h)
        def go():
            self._send("LOOP 0"); time.sleep(0.05)
            self._send("BEGIN 1"); time.sleep(0.05)
            self._send(self._build_step_cmd()); time.sleep(0.05)
            self._send("END")
        threading.Thread(target=go, daemon=True).start()

    def _preview_step(self):
        self._draw_servo_indicator(self._angle_var.get(), home=self._home_var.get())
        self._log_info(f"預覽: LOOP 0 | BEGIN 1 | {self._build_step_cmd()} | END")

    def _load_example(self):
        self._script_text.delete("1.0","end")
        self._script_text.insert("1.0",
            "# STEP 格式：delay_ms servo_id angle speed duration_ms [home]\n"
            "# home=1（預設）→ 執行完回到 0°\n"
            "# home=0        → 停在目標角度\n"
            "#\n"
            "# 範例 A：單顆 Servo 按 3 次（Servo 1 接 D9）\n"
            "ATTACH 1 9\n"
            "LOOP 0\n"
            "BEGIN 3\n"
            "STEP 1000 1 90 60 300 1\n"
            "STEP 1000 1 90 60 300 1\n"
            "STEP 1000 1 90 60 300 1\n"
            "END\n"
            "#\n"
            "# 範例 B：Ctrl+Alt+Del（3 顆依序按住）\n"
            "# ATTACH 1 9\n"
            "# ATTACH 2 10\n"
            "# ATTACH 3 11\n"
            "# LOOP 0\n"
            "# BEGIN 5\n"
            "# STEP 0   1 90 60 200 0\n"
            "# STEP 200 2 90 60 200 0\n"
            "# STEP 200 3 90 60 200 1\n"
            "# STEP 500 2 0  60 0   1\n"
            "# STEP 0   1 0  60 0   1\n"
            "# END\n"
        )

    def _run_script(self):
        if not self._serial.is_connected: self._log_info("⚠  未連線"); return
        raw   = self._script_text.get("1.0","end").splitlines()
        lines = [l.strip() for l in raw if l.strip() and not l.strip().startswith("#")]
        if not lines: messagebox.showwarning("腳本為空","請輸入腳本內容"); return
        if self._loop_var.get():
            lines = [l for l in lines if not l.startswith("LOOP")]
            lines.insert(0,"LOOP 1")
        def send_all():
            for line in lines: self._send(line); time.sleep(0.06)
        threading.Thread(target=send_all, daemon=True).start()

    # ── Serial Log ────────────────────────

    def _on_line_received(self, line):
        self.after(0, lambda: self._log_rx(line))

    def _log_rx(self, line):
        if line.startswith("OK IDLE") and "ATTACHED=" in line:
            self._parse_status_attached(line)
        if line.startswith("OK ATTACH "):
            parts = line.split()
            if len(parts) >= 3:
                try:
                    idx = int(parts[2]) - 1
                    if 0 <= idx < MAX_SERVOS:
                        self._attached[idx] = True; self._update_servo_row(idx)
                except ValueError: pass
        elif line.startswith("OK DETACH "):
            parts = line.split()
            if len(parts) >= 3:
                try:
                    idx = int(parts[2]) - 1
                    if 0 <= idx < MAX_SERVOS:
                        self._attached[idx] = False; self._update_servo_row(idx)
                except ValueError: pass
        if line.startswith("OK IDLE") or line in ("OK READY","OK DONE","OK PONG","OK STOPPED"):
            tag = "ok_ready"
        elif line.startswith("OK RUNNING") or line.startswith("OK LOOP"):
            tag = "ok_running"
        elif line.startswith("OK ATTACH") or line.startswith("OK DETACH"):
            tag = "ok_other"
        elif line.startswith("ERR"):
            tag = "err"
        else:
            tag = "ok_other"
        self._append_log(f"← {line}", tag)

    def _log_send(self, cmd): self._append_log(f"→ {cmd}", "send")
    def _log_info(self, msg): self._append_log(f"   {msg}", "info")

    def _append_log(self, text, tag):
        ts = datetime.now().strftime("%H:%M:%S")
        self._log.config(state="normal")
        self._log.insert("end", f"{ts}  ", "ts")
        self._log.insert("end", text + "\n", tag)
        self._log.see("end"); self._log.config(state="disabled")
        lines = int(self._log.index("end-1c").split(".")[0])
        self._lbl_count.config(text=f"{lines} 行")

    def _clear_log(self):
        self._log.config(state="normal"); self._log.delete("1.0","end"); self._log.config(state="disabled")
        self._lbl_count.config(text="0 行")

    def on_close(self):
        self._serial.disconnect(); self.destroy()


if __name__ == "__main__":
    app = SerialTester()
    app.protocol("WM_DELETE_WINDOW", app.on_close)
    try:
        import ctypes
        HWND = ctypes.windll.user32.GetParent(app.winfo_id())
        ctypes.windll.dwmapi.DwmSetWindowAttribute(HWND, 20, ctypes.byref(ctypes.c_int(1)), 4)
    except Exception:
        pass
    app.mainloop()
