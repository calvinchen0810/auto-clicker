# auto-clicker

Arduino Nano + Servo 自動按鍵控制器

---

## 專案結構

```
auto-clicker/
│
├── arduino/
│   └── servo_controller/
│       └── servo_controller.ino    ← Arduino IDE 2 主程式
│
├── wokwi/
│   ├── diagram.json                ← Wokwi 電路圖
│   └── README.md                   ← 模擬器操作說明
│
├── tools/
│   └── serial_tester/
│       ├── serial_tester.py        ← tkinter 桌面測試工具
│       ├── requirements.txt
│       └── README.md
│
└── server/                         ← HTTP Server（Web UI + REST API）
    ├── main.py                     ← EXE 進入點
    ├── server.py                   ← FastAPI + WebSocket
    ├── serial_manager.py           ← PySerial 通訊層
    ├── static/index.html           ← Web UI（純 HTML + Vanilla JS）
    ├── build.py                    ← PyInstaller 打包腳本
    ├── server.spec                 ← PyInstaller 設定
    ├── rthook_asyncio.py           ← EXE asyncio 修正
    ├── requirements.txt
    └── README.md
```

---

## 硬體

- Arduino Nano ATmega328P
- SG90 Servo（或相容 5V Servo）

```
Arduino Nano D9  → Servo 訊號（橘/黃）
Arduino Nano 5V  → Servo 電源（紅）     ← 建議外接 5V
Arduino Nano GND → Servo 接地（棕/黑）
```

---

## 使用方式

### 1. 燒錄 Arduino

Arduino IDE 2 開啟 `arduino/servo_controller/servo_controller.ino` 上傳。
鮑率 `115200`，Serial Monitor 顯示 `OK READY` 表示成功。

### 2. Wokwi 模擬（不需要硬體）

參考 `wokwi/README.md`。

### 3. tkinter 桌面測試工具

```bash
cd tools/serial_tester
pip install pyserial
python serial_tester.py
```

### 4. HTTP Server（Web UI + API）

```bash
cd server
pip install -r requirements.txt
python main.py
# 開啟瀏覽器：http://localhost:7070
```

打包成 EXE（Windows）：
```bash
python build.py --clean
# 輸出：dist/ServoServer.exe
```

---

## Serial 協定

鮑率：`115200`

```
STEP 格式：delay_ms angle speed duration_ms [home]
  home=1（預設）→ 執行完回到 0°
  home=0        → 停在目標角度
```

| 指令 | 說明 |
|------|------|
| `PING` | 確認連線 → `OK PONG` |
| `STATUS` | 查詢狀態 |
| `LOOP 0/1` | 設定循環 |
| `BEGIN n` | 開始傳腳本 |
| `STEP ...` | 新增步驟 |
| `END` | 執行腳本 |
| `STOP` | 立即停止並歸位 |

---

## HTTP API（Server 啟動後）

```
Web UI  : http://localhost:7070
API文件 : http://localhost:7070/docs
WS      : ws://localhost:7070/ws
```

外部程式呼叫範例：
```python
import requests
requests.post("http://localhost:7070/api/run", json={
    "loop": False,
    "steps": [
        {"delay_ms": 2000, "angle": 90, "speed": 60, "duration_ms": 300, "home": 1},
    ]
})
```
