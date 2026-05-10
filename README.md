# auto-clicker

Arduino Nano + SG90 Servo 自動按鍵控制器，最多支援 6 顆 Servo 同時控制。

---

## 目錄

- [專案結構](#專案結構)
- [硬體清單](#硬體清單)
- [Arduino 設定](#arduino-設定)
- [接線說明](#接線說明)
  - [單顆 Servo](#單顆-servo)
  - [多顆 Servo（最多 6 顆）](#多顆-servo最多-6-顆)
  - [供電方案](#供電方案)
- [燒錄程式](#燒錄程式)
- [Serial 協定](#serial-協定)
- [使用方式](#使用方式)
- [HTTP API](#http-api)

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
│   ├── diagram.json                ← Wokwi 瀏覽器模擬電路圖
│   └── README.md                   ← 模擬器操作說明
│
├── tools/
│   └── serial_tester/
│       ├── serial_tester.py        ← Python tkinter 桌面測試工具
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

## 硬體清單

| 零件 | 規格 | 數量 |
|------|------|------|
| Arduino Nano | ATmega328P（舊版或新版 bootloader）| 1 |
| SG90 Servo | 5V，180° | 1–6 |
| USB-C 轉杜邦線 | 引出 5V / GND | 1（多 Servo 供電用）|
| 杜邦線 | 公對公 / 公對母 | 若干 |

> ⚠️ 建議選購 **22AWG（或更粗）** 的 USB-C 轉杜邦線，細線最大電流只有 500mA 容易過熱。

---

## Arduino 設定

### 確認板子版本

翻到 Arduino Nano 背面，查看晶片上的文字：

| 晶片標示 | 版本 | 常見來源 |
|---------|------|---------|
| `MEGA328P` | 舊版（Old Bootloader）| 官方、早期副廠 |
| `MEGA328P` + 板子較新 | 新版（New Bootloader）| 近期淘寶/蝦皮副廠 |

不確定版本時，先用**舊版**設定嘗試上傳，失敗再換新版。

### Arduino IDE 2 板子設定

```
Tools → Board → Arduino AVR Boards → Arduino Nano

Tools → Processor：
  舊版 → ATmega328P
  新版 → ATmega328P (Old Bootloader)   ← 副廠常用這個

Tools → Port → COMx（插入 USB 後出現的 port）
```

### 安裝 CH340 驅動（副廠 Nano 必要）

副廠 Arduino Nano 通常使用 CH340 USB 晶片，Windows 需要安裝驅動：

👉 https://www.wch.cn/downloads/CH341SER_EXE.html

安裝後重新插拔 USB，裝置管理員應出現：
```
連接埠 (COM 和 LPT)
  └── USB-SERIAL CH340 (COM3)   ← 數字依電腦而異
```

---

## 接線說明

### SG90 線色對應

| 線色 | 功能 |
|------|------|
| 橘色 / 黃色 | 訊號（PWM）|
| 紅色 | 電源 5V |
| 棕色 / 黑色 | 接地 GND |

---

### 單顆 Servo

```
Arduino Nano          SG90 Servo
─────────────         ──────────
D9           ──────── 訊號（橘/黃）
5V           ──────── 電源（紅）
GND          ──────── 接地（棕/黑）

USB Type-B   ──────── 電腦（Serial 資料 + 電源）
```

Serial 指令設定：
```
ATTACH 1 9     ← Servo 1 接在 D9
```

---

### 多顆 Servo（最多 6 顆）

Arduino Nano 可用 PWM 腳位：`D3, D5, D6, D9, D10, D11`

建議腳位對應（可依需求更改，透過 ATTACH 指令設定）：

| Servo ID | 建議腳位 | 備註 |
|---------|---------|------|
| Servo 1 | D9 | Timer1，最穩定 |
| Servo 2 | D10 | Timer1 |
| Servo 3 | D11 | Timer2 |
| Servo 4 | D6 | Timer0 |
| Servo 5 | D5 | Timer0 |
| Servo 6 | D3 | Timer2 |

```
                    Arduino Nano
                    ┌───────────┐
   USB-C 轉杜邦 ──→ │5V         │
   (外部 5V 供電)   │           │D9  ──→ Servo 1 訊號（橘）
                    │           │D10 ──→ Servo 2 訊號（橘）
   電腦 USB ──────→ │USB        │D11 ──→ Servo 3 訊號（橘）
   (Serial 資料)    │           │D6  ──→ Servo 4 訊號（橘）
                    │           │D5  ──→ Servo 5 訊號（橘）
   USB-C GND ─────→ │GND        │D3  ──→ Servo 6 訊號（橘）
                    └───────────┘

   USB-C 5V ──┬──→ Servo 1 電源（紅）
              ├──→ Servo 2 電源（紅）
              ├──→ Servo 3 電源（紅）
              ├──→ Servo 4 電源（紅）
              ├──→ Servo 5 電源（紅）
              └──→ Servo 6 電源（紅）

   GND ───────┬──→ Servo 1 接地（棕/黑）
   (共同接地)  ├──→ Servo 2 接地（棕/黑）
              ├──→ Servo 3 接地（棕/黑）
              ├──→ Servo 4 接地（棕/黑）
              ├──→ Servo 5 接地（棕/黑）
              └──→ Servo 6 接地（棕/黑）
```

> ⚠️ **GND 必須共地**：Arduino GND、USB-C GND、所有 Servo GND 接在一起

Serial 指令設定（依實際接線）：
```
ATTACH 1 9
ATTACH 2 10
ATTACH 3 11
```

---

### 供電方案

#### 方案 A：單 USB 供電（1–2 顆，輕度使用）

```
電腦 USB ──→ Arduino USB（Serial 資料 + 所有電源）
Servo 電源紅線 ──→ Arduino 5V 腳
```

| 項目 | 數值 |
|------|------|
| 可用電流 | ~500mA |
| 建議 Servo 數 | 1–2 顆 |
| 限制 | USB 電流不足時 Arduino 可能重啟 |

#### 方案 B：雙 USB 供電（推薦，1–6 顆）✅

```
電腦 USB-A / USB-B ──→ Arduino USB（只傳 Serial 資料）
電腦 USB-C Port B  ──→ USB-C 轉杜邦線
                            5V  ──→ Arduino 5V 腳（繞過穩壓器）
                            GND ──→ Arduino GND
                        所有 Servo 電源也從這條 5V 取電
```

| 項目 | 數值 |
|------|------|
| 可用電流 | 900mA–1500mA |
| 建議 Servo 數 | 最多 6 顆（依序動作）|
| 優點 | Serial 與電源分離，穩定不互相干擾 |

> ⚠️ **重要**：USB-C 轉杜邦線的 5V 必須接 Arduino **5V 腳**，**不是 VIN 腳**。
>
> VIN 需要 7–12V 輸入，接 5V 會因穩壓器壓差不足導致輸出電壓只有 3.8V。

#### 電流參考（SG90）

| 狀態 | 單顆電流 | 6 顆依序動作峰值 |
|------|---------|----------------|
| 待機停止 | 10mA | 60mA |
| 空載轉動 | 150–200mA | 200mA（同時只有 1 顆動）|
| 輕載按壓 | 200–350mA | 350mA |
| 堵轉峰值 | 500–700mA | 700mA |

依序動作的場景，同一時間只有 1 顆 Servo 在移動，峰值電流遠低於 6 顆加總。

---

## 燒錄程式

1. 開啟 `arduino/servo_controller/servo_controller.ino`
2. 設定板子、處理器、Port（見 [Arduino 設定](#arduino-設定)）
3. 點擊 **→ Upload（上傳）**
4. 上傳成功後，開啟 **Serial Monitor**（右上角圖示）
5. 設定鮑率：**115200**
6. 看到以下訊息表示成功：
   ```
   OK READY
   ```
7. 輸入 `PING` 測試，應回應：
   ```
   OK PONG
   ```

---

## Serial 協定

鮑率：`115200`

### 指令總覽

| 指令 | 格式 | 說明 | 回應 |
|------|------|------|------|
| PING | `PING` | 確認連線 | `OK PONG` |
| STATUS | `STATUS` | 查詢狀態 | `OK IDLE ATTACHED=1,2` |
| ATTACH | `ATTACH sid pin` | 註冊 Servo | `OK ATTACH 1 9` |
| DETACH | `DETACH sid` | 釋放 Servo | `OK DETACH 1` |
| LOOP | `LOOP 0/1` | 設定循環 | `OK LOOP 0` |
| BEGIN | `BEGIN n` | 開始傳腳本 | `OK RECEIVING` |
| STEP | `STEP d sid a sp dur [home]` | 新增步驟 | `OK STEP n` |
| END | `END` | 腳本傳完執行 | `OK RUNNING` |
| STOP | `STOP` | 停止，所有 Servo 歸位 | `OK STOPPED` |

### ATTACH — 動態註冊 Servo

```
ATTACH sid pin

sid  = Servo 編號（1–6）
pin  = Arduino 腳位（建議 D3/D5/D6/D9/D10/D11）

範例：
ATTACH 1 9     ← Servo 1 接在 D9
ATTACH 2 10    ← Servo 2 接在 D10
ATTACH 3 11    ← Servo 3 接在 D11
```

- 執行後 Servo 自動歸位到 0°
- 可在腳本執行中途以外隨時 ATTACH
- 已 ATTACH 的 Servo 重新 ATTACH 會先 detach 再重新設定

### STEP — 腳本步驟

```
STEP delay_ms servo_id angle speed duration_ms [home]

delay_ms    = 執行前等待毫秒（0–65535）
servo_id    = Servo 編號（1–6，必須已 ATTACH）
angle       = 目標角度（0–180）
speed       = 移動速度（1–100，100=最快）
duration_ms = 到達後停留毫秒（0–65535）
home        = 執行完是否歸位（0=停住, 1=回 0°，可省略，預設 1）
```

### STATUS 回應說明

```
OK IDLE ATTACHED=1,2,3    ← 閒置，已 ATTACH Servo 1、2、3
OK IDLE ATTACHED=0        ← 閒置，尚未 ATTACH 任何 Servo
OK RUNNING 2/6            ← 執行中，目前第 2 步，共 6 步
```

### 錯誤回應

| 回應 | 說明 |
|------|------|
| `ERR INVALID_SERVO` | servo_id 超出 1–6 範圍 |
| `ERR NOT_ATTACHED` | 該 servo_id 尚未 ATTACH |
| `ERR BUSY` | 腳本執行中，無法接受新指令 |
| `ERR OVERFLOW` | 步數超過上限（48 步）|
| `ERR PARSE` | 指令格式錯誤 |
| `ERR STEP_MISMATCH` | 實際步數與 BEGIN 宣告不符 |
| `ERR NO_BEGIN` | 收到 END 但未先執行 BEGIN |
| `ERR UNKNOWN` | 未知指令 |

---

### 完整使用範例

#### 單顆 Servo 基本測試

```
ATTACH 1 9
PING
STATUS
LOOP 0
BEGIN 1
STEP 1000 1 90 60 300 1
END
```

#### Ctrl + Alt + Del（3 顆依序按住）

```
ATTACH 1 9
ATTACH 2 10
ATTACH 3 11

LOOP 0
BEGIN 5
STEP 0   1 90 60 200 0   ← Servo1 按下 Ctrl，停住
STEP 200 2 90 60 200 0   ← Servo2 按下 Alt，停住
STEP 200 3 90 60 200 1   ← Servo3 按下 Del，歸位放開
STEP 500 2 0  60 0   1   ← Servo2 放開 Alt
STEP 0   1 0  60 0   1   ← Servo1 放開 Ctrl
END
```

#### 循環連按（單顆）

```
ATTACH 1 9
LOOP 1
BEGIN 1
STEP 500 1 90 80 200 1
END
```
持續每 500ms 按一次，直到送出 `STOP`。

---

## 使用方式

### 1. Wokwi 瀏覽器模擬（不需要硬體）

參考 `wokwi/README.md`，在瀏覽器模擬 Arduino + Servo。

### 2. tkinter 桌面測試工具

```bash
cd tools/serial_tester
pip install pyserial
python serial_tester.py
```

### 3. HTTP Server（Web UI + REST API）

```bash
cd server
pip install -r requirements.txt
python main.py
```

開啟瀏覽器：**http://localhost:7070**

打包成 EXE（Windows）：
```bash
python build.py --clean
# 輸出：dist/ServoServer.exe
```

---

## HTTP API

Server 啟動後：

```
Web UI  : http://localhost:7070
API 文件 : http://localhost:7070/docs
WebSocket: ws://localhost:7070/ws
```

外部程式呼叫範例：
```python
import requests

# 先 ATTACH Servo
requests.post("http://localhost:7070/api/send",
              json={"cmd": "ATTACH 1 9"})

# 執行腳本
requests.post("http://localhost:7070/api/run", json={
    "loop": False,
    "steps": [
        {"delay_ms": 1000, "servo_id": 1, "angle": 90,
         "speed": 60, "duration_ms": 300, "home": 1},
    ]
})
```
