# auto-clicker

Arduino Nano + SG90 Servo 自動按鍵控制器，最多同時支援 6 顆 Servo。

---

## 目錄

- [硬體需求](#硬體需求)
- [專案結構](#專案結構)
- [Arduino 設定與燒錄](#arduino-設定與燒錄)
- [接線說明](#接線說明)
- [工具選擇](#工具選擇)
- [tkinter 測試工具](#tkinter-測試工具)
- [HTTP Server（Web UI）](#http-server-web-ui)
- [Serial 協定參考](#serial-協定參考)

---

## 硬體需求

| 零件 | 規格 | 數量 |
|------|------|------|
| Arduino Nano | ATmega328P | 1 |
| SG90 Servo | 5V，180° | 1–6 |
| USB-C 轉杜邦線 | 22AWG，引出 5V/GND | 1（多 Servo 建議）|
| 杜邦線 | 公對公 / 公對母 | 若干 |

---

## 專案結構

```
auto-clicker/
├── arduino/
│   └── servo_controller/
│       └── servo_controller.ino    ← Arduino IDE 2 主程式
│
├── wokwi/
│   ├── diagram.json                ← Wokwi 瀏覽器模擬電路圖
│   └── README.md
│
├── tools/
│   └── serial_tester/
│       ├── serial_tester.py        ← Python tkinter 桌面測試工具
│       ├── requirements.txt
│       └── README.md
│
└── server/
    ├── main.py                     ← EXE 進入點
    ├── server.py                   ← FastAPI + WebSocket
    ├── serial_manager.py           ← PySerial 通訊層
    ├── static/index.html           ← Web UI（純 HTML）
    ├── build.py                    ← PyInstaller 打包腳本
    ├── server.spec
    ├── rthook_asyncio.py
    ├── requirements.txt
    └── README.md
```

---

## Arduino 設定與燒錄

### 1. 安裝 Arduino IDE 2

下載：https://www.arduino.cc/en/software

### 2. 確認板子版本

| 版本 | 常見來源 | Processor 設定 |
|------|---------|---------------|
| 舊版原廠 | Arduino 官方 | `ATmega328P` |
| 新版副廠 | 淘寶/蝦皮 | `ATmega328P (Old Bootloader)` |

### 3. 安裝 CH340 驅動（副廠必要）

👉 https://www.wch.cn/downloads/CH341SER_EXE.html

安裝後重新插拔 USB，裝置管理員應出現：
```
連接埠 → USB-SERIAL CH340 (COMx)
```

### 4. Arduino IDE 設定

```
Tools → Board      → Arduino AVR Boards → Arduino Nano
Tools → Processor  → ATmega328P（或 Old Bootloader）
Tools → Port       → COMx（插入後出現的）
```

### 5. 燒錄

1. 開啟 `arduino/servo_controller/servo_controller.ino`
2. 點擊 **→ Upload**
3. 開啟 Serial Monitor，鮑率設 **115200**
4. 看到 `OK READY` 表示成功
5. 輸入 `PING`，應回應 `OK PONG`

---

## 接線說明

### SG90 線色

| 線色 | 功能 |
|------|------|
| 橘/黃 | 訊號（PWM）|
| 紅 | 電源 5V |
| 棕/黑 | 接地 GND |

### 單顆 Servo

```
Arduino Nano D9  → Servo 訊號（橘）
Arduino Nano 5V  → Servo 電源（紅）
Arduino Nano GND → Servo 接地（棕）
Arduino USB      → 電腦（Serial + 電源）
```

燒錄後設定：
```
ATTACH 1 9
```

### 多顆 Servo（最多 6 顆）

**建議腳位：**

| Servo ID | 腳位 |
|---------|------|
| S1 | D9 |
| S2 | D10 |
| S3 | D11 |
| S4 | D6 |
| S5 | D5 |
| S6 | D3 |

**接線：**

```
電腦 USB-A ──────────→ Arduino USB（Serial 資料）
電腦 USB-C Port B ───→ USB-C 轉杜邦線
                           5V  → Arduino 5V 腳（⚠ 不是 VIN）
                           GND → Arduino GND（共地）
                           5V  → 所有 Servo 紅線
                           GND → 所有 Servo 棕線

Arduino D9  → Servo 1 橘線
Arduino D10 → Servo 2 橘線
Arduino D11 → Servo 3 橘線
```

> ⚠️ USB-C 5V 必須接 Arduino **5V 腳**，不是 VIN  
> ⚠️ 所有 GND 必須共地（Arduino + 外部電源 + 所有 Servo）

### 供電能力

| 供電方式 | 建議 Servo 數 |
|---------|-------------|
| 單 USB 供電 | 1–2 顆 |
| 雙 USB（資料 + 外部 5V）| 最多 6 顆（依序動作）|

---

## 工具選擇

| 工具 | 適合場景 |
|------|---------|
| **tkinter 測試工具** | 桌面 GUI，快速測試單顆或多顆 Servo |
| **Web UI（HTTP Server）** | 瀏覽器控制，支援外部程式 HTTP 呼叫 |
| **Wokwi 模擬** | 不需硬體，在瀏覽器驗證程式邏輯 |

---

## tkinter 測試工具

### 環境建立

```bash
cd tools/serial_tester
pip install pyserial
```

### 啟動

```bash
python serial_tester.py
```

### 介面說明

三欄佈局：

**左欄 — Servo 管理**
- S1–S6 各一列，顯示連接狀態（● 綠=已連接）
- 腳位輸入框（未連接時可編輯）
- [ATTACH] / [DETACH] 按鈕
- [全部 ATTACH] / [全部 DETACH] 批次操作

**中欄 — 測試區**
- 單步測試：設定 延遲/ServoID/角度/速度/停留/歸位，點「▶ 送出」
- 腳本測試：直接編輯 `ATTACH/LOOP/BEGIN/STEP/END` 指令
- 範例 A（單顆）、範例 B（Ctrl+Alt+Del）

**右欄 — Serial Log**
- 即時顯示所有往來指令，顏色分類
- 手動輸入任意 Serial 指令

### 使用步驟

```
1. 插入 Arduino → 工具自動偵測（⭐ 標記）
2. 點 [連線]
3. 在 Servo 管理區設定腳位 → 點 [ATTACH]
4. 單步測試：選 Servo ID → 設定參數 → [▶ 送出單步]
5. 腳本測試：點 [載入範例] → [▶ 執行腳本]
```

詳細說明：`tools/serial_tester/README.md`

---

## HTTP Server（Web UI）

### 環境建立

```bash
cd server
pip install -r requirements.txt
```

### 啟動

```bash
python main.py
```

啟動後 Console 顯示：
```
╔══════════════════════════════════════╗
║     Servo Controller Server          ║
╠══════════════════════════════════════╣
║  Web UI : http://127.0.0.1:7070     ║
║  API    : http://127.0.0.1:7070/docs║
╠══════════════════════════════════════╣
║  Arduino: COM3                       ║
╚══════════════════════════════════════╝
```

### 打包 EXE

```bash
python build.py --clean
# 輸出：dist/ServoServer.exe
```

### 使用步驟

```
1. 執行 python main.py（或 ServoServer.exe）
2. 瀏覽器開啟 http://localhost:7070
3. 選擇 COM port → 點 [CONNECT]
4. Servo 管理區：設定腳位 → 點 [ATTACH]
5. 單步測試 或 腳本編輯器 執行動作
```

### 外部程式呼叫

```python
import requests
BASE = "http://localhost:7070"

requests.post(f"{BASE}/api/attach", json={"sid": 1, "pin": 9})
requests.post(f"{BASE}/api/run", json={
    "loop": False,
    "steps": [
        {"delay_ms": 1000, "servo_id": 1, "angle": 90,
         "speed": 60, "duration_ms": 300, "home": 1}
    ]
})
```

詳細說明：`server/README.md`

---

## Serial 協定參考

鮑率：`115200`

### 主要指令

```
ATTACH sid pin          → OK ATTACH sid pin
DETACH sid              → OK DETACH sid
PING                    → OK PONG
STATUS                  → OK IDLE ATTACHED=1,2,3
LOOP 0/1                → OK LOOP 0/1
BEGIN n                 → OK RECEIVING
STEP d sid a sp dur [h] → OK STEP n
END                     → OK RUNNING
STOP                    → OK STOPPED
```

### STEP 格式

```
STEP delay_ms servo_id angle speed duration_ms [home]

delay_ms   : 0–65535  執行前等待 ms
servo_id   : 1–6      要動哪顆（需先 ATTACH）
angle      : 0–180    目標角度
speed      : 1–100    移動速度
duration_ms: 0–65535  停留 ms
home       : 0/1      執行完是否回 0°（預設 1）
```

### 常用範例

```
# 單顆基本測試
ATTACH 1 9
PING
BEGIN 1
STEP 500 1 90 60 300 1
END

# Ctrl+Alt+Del（3 顆依序按住）
ATTACH 1 9
ATTACH 2 10
ATTACH 3 11
LOOP 0
BEGIN 5
STEP 0   1 90 60 200 0
STEP 200 2 90 60 200 0
STEP 200 3 90 60 200 1
STEP 500 2 0  60 0   1
STEP 0   1 0  60 0   1
END
```
