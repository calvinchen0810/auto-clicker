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

接線：

```
Arduino Nano D9  → Servo 訊號（橘）
Arduino Nano 5V  → Servo 電源（紅）
Arduino Nano GND → Servo 接地（黑）
```

---

## 開始使用

### 1. 燒錄 Arduino

用 Arduino IDE 2 開啟 `arduino/servo_controller/servo_controller.ino` 並上傳。

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

```
PING                         → OK PONG
STATUS                       → OK IDLE / OK RUNNING n/total
LOOP 0                       → OK LOOP 0
BEGIN n                      → OK RECEIVING
STEP delay_ms angle speed duration_ms → OK STEP n
END                          → OK RUNNING
STOP                         → OK STOPPED
```
