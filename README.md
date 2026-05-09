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
│   ├── diagram.json                ← Wokwi 電路圖（Arduino Nano + Servo）
│   └── README.md                   ← 模擬器使用說明
│
└── tools/
    └── serial_tester/
        ├── serial_tester.py        ← Python tkinter Serial 測試工具
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

## 開始使用

### 1. 燒錄 Arduino

用 Arduino IDE 2 開啟 `arduino/servo_controller/servo_controller.ino` 並上傳。
Serial 鮑率：`115200`，上傳成功後 Serial Monitor 顯示 `OK READY`。

### 2. 模擬測試（不需要硬體）

參考 `wokwi/README.md`，在瀏覽器模擬 Arduino + Servo 行為。

### 3. 實機測試工具

```bash
cd tools/serial_tester
pip install pyserial
python serial_tester.py
```

---

## Serial 協定

鮑率：`115200`

### 指令格式

```
PING                                   → OK PONG
STATUS                                 → OK IDLE / OK RUNNING n/total
LOOP 0/1                               → OK LOOP 0/1
BEGIN n                                → OK RECEIVING
STEP delay_ms angle speed duration_ms [home]  → OK STEP n
END                                    → OK RUNNING
STOP                                   → OK STOPPED
```

### STEP 參數

| 參數 | 範圍 | 說明 |
|------|------|------|
| `delay_ms` | 0–65535 | 執行前等待毫秒 |
| `angle` | 0–180 | Servo 目標角度 |
| `speed` | 1–100 | 移動速度（100=最快）|
| `duration_ms` | 0–65535 | 到達後停留毫秒 |
| `home` | 0 或 1（**可省略，預設 1**）| 執行完是否歸位到 0° |

### home 參數

| 值 | 行為 |
|----|------|
| `1`（預設）| 執行完自動回到 0°（向下相容）|
| `0` | 停在目標角度不歸位 |

> `STOP` 無論 home 設定為何，都會強制歸位到 0°

### 使用範例

```
# 按 3 次，每次自動歸位
LOOP 0
BEGIN 3
STEP 2000 90 60 300 1
STEP 1000 90 60 300 1
STEP 1000 90 60 300 1
END

# 連續移動不歸位，最後才回 0°
LOOP 0
BEGIN 3
STEP 0 45 80 200 0
STEP 0 90 80 200 0
STEP 0 135 80 300 1
END
```
