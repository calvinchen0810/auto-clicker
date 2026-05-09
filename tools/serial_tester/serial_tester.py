"""
tools/serial_tester/serial_tester.py

Arduino Servo Serial Test Tool
- Connect to a real Arduino (USB)
- Send serial commands and view responses
- Test single-step motion / full scripts / emergency stop

STEP format: delay_ms angle speed duration_ms [home]
    home=1 (default) -> Return to 0 deg after execution
    home=0           -> Stay at target angle (no homing)

Run:
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
#  Color settings
# ─────────────────────────────────────────
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
FONT_MONO  = ("Consolas", 12)
FONT_UI    = ("Segoe UI", 12)
FONT_UI_B  = ("Segoe UI", 12, "bold")
FONT_TITLE = ("Segoe UI", 12, "bold")


# ─────────────────────────────────────────
#  Serial manager
# ─────────────────────────────────────────
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


# ─────────────────────────────────────────
#  Main window
# ─────────────────────────────────────────
class SerialTester(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Servo Serial Tester")
        self.geometry("1200x900")
        self.configure(bg=BG)
        self.resizable(True, True)

        self._serial = SerialManager(self._on_line_received)
        self._build_ui()
        self._refresh_ports()

    # ── UI construction ───────────────────

    def _build_ui(self):
        # Top connection bar
        top = tk.Frame(self, bg=BG_PANEL, pady=8, padx=12)
        top.pack(fill="x")

        tk.Label(top, text="Servo Serial Tester", bg=BG_PANEL, fg=FG,
                 font=FONT_TITLE).pack(side="left")

        self._dot = tk.Label(top, text="●", bg=BG_PANEL, fg=RED, font=("Consolas", 14))
        self._dot.pack(side="left", padx=(16, 4))
        self._lbl_state = tk.Label(top, text="Disconnected", bg=BG_PANEL, fg=FG_DIM, font=FONT_UI)
        self._lbl_state.pack(side="left")

        tk.Label(top, text="  Port:", bg=BG_PANEL, fg=FG_DIM, font=FONT_UI).pack(side="left")
        self._port_var = tk.StringVar()
        self._port_cb  = ttk.Combobox(top, textvariable=self._port_var,
                                       width=28, font=FONT_MONO, state="readonly")
        self._port_cb.pack(side="left", padx=4)

        tk.Button(top, text="⟳", bg=BG_INPUT, fg=FG_DIM, font=FONT_UI,
                  bd=0, padx=6, cursor="hand2",
                  command=self._refresh_ports).pack(side="left")

        self._btn_conn = tk.Button(top, text="Connect", bg="#166534", fg="#bbf7d0",
                                   font=FONT_UI_B, bd=0, padx=12, pady=4,
                                   cursor="hand2", command=self._toggle_connect)
        self._btn_conn.pack(side="left", padx=(8, 0))

        # Main split layout
        body = tk.Frame(self, bg=BG)
        body.pack(fill="both", expand=True, padx=10, pady=8)
        body.columnconfigure(0, weight=1)
        body.columnconfigure(1, weight=1)
        body.rowconfigure(0, weight=1)

        left = tk.Frame(body, bg=BG)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 5))
        self._build_left(left)

        right = tk.Frame(body, bg=BG)
        right.grid(row=0, column=1, sticky="nsew", padx=(5, 0))
        self._build_log(right)

    def _build_left(self, parent):
        parent.rowconfigure(0, weight=0)
        parent.rowconfigure(1, weight=0)
        parent.rowconfigure(2, weight=1)
        parent.columnconfigure(0, weight=1)

        # ── Quick commands ─────────────────
        grp1 = self._group(parent, "Quick Commands")
        grp1.grid(row=0, column=0, sticky="ew", pady=(0, 6))

        row = tk.Frame(grp1, bg=BG_PANEL)
        row.pack(fill="x", padx=8, pady=8)
        for text, color, cmd in [
            ("PING",   BLUE,  lambda: self._send("PING")),
            ("STATUS", AMBER, lambda: self._send("STATUS")),
            ("STOP",   RED,   lambda: self._send("STOP")),
        ]:
            tk.Button(row, text=text, bg=BG_INPUT, fg=color, font=FONT_UI_B,
                      bd=0, padx=14, pady=6, cursor="hand2",
                      command=cmd).pack(side="left", padx=4)

        # ── Single-step test ───────────────
        grp2 = self._group(parent, "Single-Step Test")
        grp2.grid(row=1, column=0, sticky="ew", pady=(0, 6))

        fields = tk.Frame(grp2, bg=BG_PANEL)
        fields.pack(fill="x", padx=8, pady=(8, 0))

        self._delay_var    = tk.IntVar(value=0)
        self._angle_var    = tk.IntVar(value=90)
        self._speed_var    = tk.IntVar(value=60)
        self._duration_var = tk.IntVar(value=300)
        self._home_var     = tk.IntVar(value=1)

        specs = [
            ("Delay ms", self._delay_var,    0, 65535),
            ("Angle degree", self._angle_var,    0, 180),
            ("Speed %",     self._speed_var,    1, 100),
            ("Duration ms",  self._duration_var, 0, 65535),
        ]
        for i, (label, var, lo, hi) in enumerate(specs):
            col = (i % 2) * 2
            r   = i // 2
            tk.Label(fields, text=label, bg=BG_PANEL, fg=FG_DIM,
                     font=FONT_UI).grid(row=r, column=col, sticky="w", padx=(4, 2), pady=3)
            tk.Spinbox(fields, from_=lo, to=hi, textvariable=var, width=8,
                       bg=BG_INPUT, fg=FG, font=FONT_MONO,
                       buttonbackground=BG_INPUT, relief="flat",
                       bd=1).grid(row=r, column=col+1, sticky="ew", padx=(0, 12), pady=3)
        fields.columnconfigure(1, weight=1)
        fields.columnconfigure(3, weight=1)

        # Home mode toggle
        home_row = tk.Frame(grp2, bg=BG_PANEL)
        home_row.pack(fill="x", padx=8, pady=(4, 0))

        tk.Label(home_row, text="Home mode", bg=BG_PANEL, fg=FG_DIM,
                 font=FONT_UI).pack(side="left", padx=(4, 8))

        # home=1 button
        self._btn_home1 = tk.Button(
            home_row, text="1  Return to 0 deg", font=FONT_UI,
            bg="#14532d", fg="#bbf7d0", bd=0, padx=10, pady=4, cursor="hand2",
            command=lambda: self._set_home(1)
        )
        self._btn_home1.pack(side="left", padx=(0, 4))

        # home=0 button
        self._btn_home0 = tk.Button(
            home_row, text="0  Stay at target", font=FONT_UI,
            bg=BG_INPUT, fg=FG_DIM, bd=0, padx=10, pady=4, cursor="hand2",
            command=lambda: self._set_home(0)
        )
        self._btn_home0.pack(side="left")

        # Angle indicator
        indicator_row = tk.Frame(grp2, bg=BG_PANEL)
        indicator_row.pack(fill="x", padx=8, pady=4)

        self._canvas = tk.Canvas(indicator_row, width=110, height=90,
                                 bg=BG_PANEL, highlightthickness=0)
        self._canvas.pack(side="left")
        self._draw_servo_indicator(0, home=1)

        # Home mode description
        self._lbl_home_desc = tk.Label(
            indicator_row,
            text="home=1\nReturn to\n0 deg",
            bg=BG_PANEL, fg=GREEN, font=("Consolas", 9),
            justify="left"
        )
        self._lbl_home_desc.pack(side="left", padx=12)

        btn_row = tk.Frame(grp2, bg=BG_PANEL)
        btn_row.pack(fill="x", padx=8, pady=8)
        tk.Button(btn_row, text="▶  Send Step", bg="#14532d", fg="#bbf7d0",
                  font=FONT_UI_B, bd=0, padx=14, pady=6, cursor="hand2",
                  command=self._send_step).pack(side="left")
        tk.Button(btn_row, text="Preview Cmd", bg=BG_INPUT, fg=FG_DIM,
                  font=FONT_UI, bd=0, padx=10, pady=6, cursor="hand2",
                  command=self._preview_step).pack(side="left", padx=8)

        # ── Script test ────────────────────
        grp3 = self._group(parent, "Script Test")
        grp3.grid(row=2, column=0, sticky="nsew")

        script_btns = tk.Frame(grp3, bg=BG_PANEL)
        script_btns.pack(fill="x", padx=8, pady=6)

        self._loop_var = tk.BooleanVar(value=False)
        tk.Checkbutton(script_btns, text="Loop", variable=self._loop_var,
                       bg=BG_PANEL, fg=FG, selectcolor=BG_INPUT,
                       activebackground=BG_PANEL, font=FONT_UI).pack(side="left")
        tk.Button(script_btns, text="Load Example", bg=BG_INPUT, fg=FG_DIM,
                  font=FONT_UI, bd=0, padx=10, pady=4, cursor="hand2",
                  command=self._load_example).pack(side="left", padx=6)
        tk.Button(script_btns, text="▶ Run Script", bg="#14532d", fg="#bbf7d0",
                  font=FONT_UI_B, bd=0, padx=12, pady=4, cursor="hand2",
                  command=self._run_script).pack(side="left", padx=4)
        tk.Button(script_btns, text="■ STOP", bg="#7f1d1d", fg="#fca5a5",
                  font=FONT_UI_B, bd=0, padx=10, pady=4, cursor="hand2",
                  command=lambda: self._send("STOP")).pack(side="left", padx=4)

        self._script_text = tk.Text(grp3, bg=BG_INPUT, fg=FG, font=FONT_MONO,
                                    insertbackground=FG, relief="flat",
                                    bd=0, padx=6, pady=6)
        self._script_text.pack(fill="both", expand=True, padx=8, pady=(0, 8))

        self._load_example()

    def _build_log(self, parent):
        grp = self._group(parent, "Serial Log")
        grp.pack(fill="both", expand=True)

        log_top = tk.Frame(grp, bg=BG_PANEL)
        log_top.pack(fill="x", padx=8, pady=(4, 0))
        tk.Button(log_top, text="Clear", bg=BG_INPUT, fg=FG_DIM,
                  font=FONT_UI, bd=0, padx=8, pady=2,
                  cursor="hand2", command=self._clear_log).pack(side="right")
        self._lbl_count = tk.Label(log_top, text="0 lines", bg=BG_PANEL,
                                   fg=FG_DIM, font=FONT_UI)
        self._lbl_count.pack(side="right", padx=8)

        self._log = scrolledtext.ScrolledText(
            grp, bg=BG, fg=GREEN, font=FONT_MONO,
            insertbackground=FG, relief="flat", bd=0,
            padx=6, pady=6, state="disabled"
        )
        self._log.pack(fill="both", expand=True, padx=8, pady=4)

        for tag, color in [
            ("ok_ready",   GREEN),
            ("ok_running", AMBER),
            ("ok_other",   "#a3e635"),
            ("err",        RED),
            ("send",       BLUE),
            ("ts",         FG_DIM),
            ("info",       FG_DIM),
        ]:
            self._log.tag_config(tag, foreground=color)

        input_row = tk.Frame(grp, bg=BG_PANEL)
        input_row.pack(fill="x", padx=8, pady=(0, 8))
        tk.Label(input_row, text=">>", bg=BG_PANEL, fg=BLUE,
                 font=FONT_MONO).pack(side="left")
        self._cmd_var = tk.StringVar()
        self._cmd_entry = tk.Entry(input_row, textvariable=self._cmd_var,
                                   bg=BG_INPUT, fg=FG, font=FONT_MONO,
                                   insertbackground=FG, relief="flat", bd=0)
        self._cmd_entry.pack(side="left", fill="x", expand=True, padx=(4, 6))
        self._cmd_entry.bind("<Return>", lambda e: self._send_manual())
        tk.Button(input_row, text="Send", bg=BG_INPUT, fg=FG,
                  font=FONT_UI, bd=0, padx=10, pady=3,
                  cursor="hand2", command=self._send_manual).pack(side="left")

    def _group(self, parent, title):
        return tk.LabelFrame(parent, text=f"  {title}  ", bg=BG_PANEL, fg=AMBER,
                             font=("Consolas", 9), bd=1, relief="groove",
                             highlightbackground=BORDER)

    # ── Home mode toggle ─────────────────

    def _set_home(self, val: int):
        self._home_var.set(val)
        if val == 1:
            self._btn_home1.config(bg="#14532d", fg="#bbf7d0")
            self._btn_home0.config(bg=BG_INPUT,  fg=FG_DIM)
            self._lbl_home_desc.config(text="home=1\nReturn to\n0 deg", fg=GREEN)
        else:
            self._btn_home1.config(bg=BG_INPUT,  fg=FG_DIM)
            self._btn_home0.config(bg="#78350f",  fg="#fde68a")
            self._lbl_home_desc.config(text="home=0\nStay at\ntarget", fg=AMBER)
        self._draw_servo_indicator(self._angle_var.get(), home=val)

    # ── Servo angle indicator ─────────────

    def _draw_servo_indicator(self, angle: int, home: int | None = None):
        import math
        if home is None:
            home = self._home_var.get()
        c = self._canvas
        c.delete("all")
        cx, cy, r = 55, 62, 40

        # Background arc (0-180 deg)
        c.create_arc(cx-r, cy-r, cx+r, cy+r, start=0, extent=180,
                     style="arc", outline=BORDER, width=2)

        # home=1: draw a dashed return path to 0 deg
        if home == 1 and angle > 0:
            c.create_arc(cx-r+6, cy-r+6, cx+r-6, cy+r-6,
                         start=90, extent=angle - 180,
                         style="arc", outline="#1a4a1a", width=1, dash=(3, 3))

        # Target angle needle
        rad = math.radians(180 - angle)
        ex  = cx + r * math.cos(rad)
        ey  = cy - r * math.sin(rad)
        color = GREEN if home == 1 else AMBER
        c.create_line(cx, cy, ex, ey, fill=color, width=2)
        c.create_oval(cx-4, cy-4, cx+4, cy+4, fill=AMBER, outline="")

        # home=1: draw the home marker at 0 deg
        if home == 1:
            c.create_oval(cx+r-4, cy-4, cx+r+4, cy+4,
                          fill="#1a4a1a", outline=GREEN, width=1)

        # Angle text
        c.create_text(cx, cy + 24, text=f"{angle}°", fill=FG, font=FONT_MONO)

    # ── Connection control ───────────────

    def _refresh_ports(self):
        ports = self._serial.scan_ports()
        items = [f"{'⭐ ' if p['likely'] else '   '}{p['port']}  {p['desc']}"
                 for p in ports]
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
            self._log_info("Disconnected")
        else:
            port = self._get_selected_port()
            if not port:
                messagebox.showerror("Error", "Please select a COM port first")
                return
            if self._serial.connect(port):
                self._set_connected(True)
                self._log_info(f"Connected to {port} (baud 115200)")
            else:
                messagebox.showerror("Connection Failed",
                    f"Cannot open {port}\nPlease make sure Arduino is connected and drivers are installed")

    def _set_connected(self, connected: bool):
        if connected:
            self._dot.config(fg=GREEN)
            self._lbl_state.config(text=f"Connected  {self._get_selected_port()}", fg=GREEN)
            self._btn_conn.config(text="Disconnect", bg="#7f1d1d", fg="#fca5a5")
        else:
            self._dot.config(fg=RED)
            self._lbl_state.config(text="Disconnected", fg=FG_DIM)
            self._btn_conn.config(text="Connect", bg="#166534", fg="#bbf7d0")

    # ── Command sending ───────────────────

    def _send(self, cmd: str) -> bool:
        if not self._serial.is_connected:
            self._log_info("⚠  Not connected")
            return False
        self._log_send(cmd)
        return self._serial.send(cmd)

    def _send_manual(self):
        cmd = self._cmd_var.get().strip()
        if cmd:
            self._send(cmd)
            self._cmd_var.set("")

    def _build_step_cmd(self) -> str:
        """Build the STEP command string from current UI values."""
        d   = self._delay_var.get()
        a   = self._angle_var.get()
        sp  = self._speed_var.get()
        dur = self._duration_var.get()
        h   = self._home_var.get()
        return f"STEP {d} {a} {sp} {dur} {h}"

    def _send_step(self):
        a = self._angle_var.get()
        h = self._home_var.get()
        self._draw_servo_indicator(a, home=h)

        # Send a single-step script (1 step only, home controls return behavior)
        def go():
            self._send("LOOP 0")
            time.sleep(0.05)
            self._send("BEGIN 1")
            time.sleep(0.05)
            self._send(self._build_step_cmd())
            time.sleep(0.05)
            self._send("END")

        threading.Thread(target=go, daemon=True).start()

    def _preview_step(self):
        a = self._angle_var.get()
        h = self._home_var.get()
        self._draw_servo_indicator(a, home=h)
        cmd = self._build_step_cmd()
        self._log_info(f"Preview: LOOP 0 | BEGIN 1 | {cmd} | END")

    def _load_example(self):
        example = (
            "# STEP format: delay_ms angle speed duration_ms [home]\n"
            "# home=1 (default) -> Return to 0 deg after each step\n"
            "# home=0           -> Stay at target angle (no homing)\n"
            "#\n"
            "# Example A: run 3 times with auto-home (home=1)\n"
            "LOOP 0\n"
            "BEGIN 3\n"
            "STEP 2000 90 60 300 1\n"
            "STEP 1000 90 60 300 1\n"
            "STEP 1000 90 60 300 1\n"
            "END\n"
            "#\n"
            "# Example B: continuous moves without homing (home=0), then home at the end\n"
            "# LOOP 0\n"
            "# BEGIN 3\n"
            "# STEP 0 45 80 200 0\n"
            "# STEP 0 90 80 200 0\n"
            "# STEP 0 135 80 300 1\n"
            "# END\n"
        )
        self._script_text.delete("1.0", "end")
        self._script_text.insert("1.0", example)

    def _run_script(self):
        if not self._serial.is_connected:
            self._log_info("⚠  Not connected")
            return

        raw   = self._script_text.get("1.0", "end").splitlines()
        lines = [l.strip() for l in raw
                 if l.strip() and not l.strip().startswith("#")]

        if not lines:
            messagebox.showwarning("Empty Script", "Please enter script content")
            return

        if self._loop_var.get():
            lines = [l for l in lines if not l.startswith("LOOP")]
            lines.insert(0, "LOOP 1")

        def send_all():
            for line in lines:
                self._send(line)
                time.sleep(0.06)

        threading.Thread(target=send_all, daemon=True).start()

    # ── Serial log ───────────────────────

    def _on_line_received(self, line: str):
        self.after(0, lambda: self._log_rx(line))

    def _log_rx(self, line: str):
        if line in ("OK READY", "OK DONE", "OK PONG", "OK IDLE", "OK STOPPED"):
            tag = "ok_ready"
        elif line.startswith("OK RUNNING") or line.startswith("OK LOOP"):
            tag = "ok_running"
        elif line.startswith("ERR"):
            tag = "err"
        else:
            tag = "ok_other"
        self._append_log(f"← {line}", tag)

    def _log_send(self, cmd: str):
        self._append_log(f"→ {cmd}", "send")

    def _log_info(self, msg: str):
        self._append_log(f"   {msg}", "info")

    def _append_log(self, text: str, tag: str):
        ts = datetime.now().strftime("%H:%M:%S")
        self._log.config(state="normal")
        self._log.insert("end", f"{ts}  ", "ts")
        self._log.insert("end", text + "\n", tag)
        self._log.see("end")
        self._log.config(state="disabled")
        lines = int(self._log.index("end-1c").split(".")[0])
        self._lbl_count.config(text=f"{lines} lines")

    def _clear_log(self):
        self._log.config(state="normal")
        self._log.delete("1.0", "end")
        self._log.config(state="disabled")
        self._lbl_count.config(text="0 lines")

    # ── Close ────────────────────────────

    def on_close(self):
        self._serial.disconnect()
        self.destroy()


# ─────────────────────────────────────────
#  Entry Point
# ─────────────────────────────────────────
if __name__ == "__main__":
    app = SerialTester()
    app.protocol("WM_DELETE_WINDOW", app.on_close)

    # Dark title bar (Windows 11)
    try:
        import ctypes
        HWND = ctypes.windll.user32.GetParent(app.winfo_id())
        ctypes.windll.dwmapi.DwmSetWindowAttribute(
            HWND, 20, ctypes.byref(ctypes.c_int(1)), 4)
    except Exception:
        pass

    app.mainloop()
