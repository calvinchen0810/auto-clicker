# Servo Serial Tester

Python tkinter GUI，用來測試 Arduino Nano + SG90 Servo，支援最多 6 顆。
不需要安裝 PyQt6，只需要 Python 內建的 tkinter + pyserial。

---

## 啟動

```bash
pip install pyserial
python serial_tester.py
```

---

## 介面說明

```
┌─ Servo Serial Tester ── ● 已連線 COM3 ── [斷線] ──────────────────────────┐
│                                                                             │
│ ┌── Servo 管理 ──────────┐  ┌── 單步測試 ─────────┐  ┌── Serial Log ─────┐ │
│ │ ID  腳位  狀態  操作   │  │ 延遲ms  [    0]      │  │ 14:02 → ATTACH 19 │ │
│ │ S1  [9 ] ● D9✓ [DETACH]│  │ Servo ID[ 1  ]      │  │ 14:02 ← OK ATTACH │ │
│ │ S2  [10] —    [ATTACH] │  │ 角度°   [  90]  ◜   │  │ 14:02 → BEGIN 1   │ │
│ │ S3  [11] —    [ATTACH] │  │ 速度    [  60]       │  │ 14:02 ← OK STEP 1 │ │
│ │ S4  [6 ] —    [ATTACH] │  │ 停留ms  [ 300]       │  │ 14:02 ← OK RUNNING│ │
│ │ S5  [5 ] —    [ATTACH] │  │ 歸位 [1 回0°][0 停住]│  │ 14:02 ← OK DONE   │ │
│ │ S6  [3 ] —    [ATTACH] │  │                      │  ├───────────────────┤ │
│ │ [全部ATTACH][全部DETACH]│  │ [▶ 送出單步][預覽]  │  │ >> [手動輸入] [送出]│ │
│ ├────────────────────────┤  └─────────────────────┘  └───────────────────┘ │
│ │ 快速指令               │                                                   │
│ │ [PING] [STATUS] [STOP] │  ┌── 腳本測試 ─────────────────────────────────┐ │
│ └────────────────────────┘  │ ☐循環 [載入範例] [▶執行腳本] [■STOP]       │ │
│                              │ ATTACH 1 9                                  │ │
│                              │ LOOP 0                                      │ │
│                              │ BEGIN 3                                     │ │
│                              │ STEP 1000 1 90 60 300 1                     │ │
│                              └─────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Servo 管理區（左欄）

### ATTACH / DETACH

| 操作 | 說明 |
|------|------|
| 腳位 Spinbox | 設定該 Servo 接在哪個腳位（2–13）|
| [ATTACH] | 送出 `ATTACH sid pin`，Servo 自動歸位到 0° |
| [DETACH] | 送出 `DETACH sid`，釋放 Servo |
| [全部 ATTACH] | 依序 ATTACH 所有 6 顆（使用各列設定的腳位）|
| [全部 DETACH] | 依序 DETACH 所有已 ATTACH 的 Servo |

**預設腳位對應：**

| Servo ID | 預設腳位 |
|---------|---------|
| S1 | D9 |
| S2 | D10 |
| S3 | D11 |
| S4 | D6 |
| S5 | D5 |
| S6 | D3 |

### 狀態同步

- 連線後自動送 `STATUS` 查詢，若 Arduino 已有 ATTACH 的 Servo 會自動反映在 UI
- `OK ATTACH` / `OK DETACH` 回應會即時更新對應列的狀態燈

---

## 單步測試區（中欄上）

| 欄位 | 說明 |
|------|------|
| 延遲 ms | 執行前等待毫秒 |
| **Servo ID** | 要動哪顆（1–6，**橘色**提示）|
| 角度 ° | 目標角度 0–180 |
| 速度 | 1–100 |
| 停留 ms | 到達後停留毫秒 |

- 若選擇的 Servo ID 尚未 ATTACH，會彈出確認對話框詢問是否先自動 ATTACH
- 角度視覺指示器即時更新

---

## 腳本測試區（中欄下）

腳本格式：`LOOP / ATTACH / BEGIN / STEP / END`，`#` 開頭為註解。

### STEP 格式

```
STEP delay_ms servo_id angle speed duration_ms [home]
```

### 範例 A：單顆 Servo 按 3 次

```
ATTACH 1 9
LOOP 0
BEGIN 3
STEP 1000 1 90 60 300 1
STEP 1000 1 90 60 300 1
STEP 1000 1 90 60 300 1
END
```

### 範例 B：Ctrl + Alt + Del（3 顆依序按住）

```
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

---

## 常見問題

**Q: 找不到 COM port？**
A: 安裝 CH340 驅動：https://www.wch.cn/downloads/CH341SER_EXE.html，插拔後點 ⟳ 刷新。

**Q: ATTACH 後 Servo 沒有動到 0°？**
A: 確認 Servo 電源已接好（5V + GND），訊號線接在對應腳位。

**Q: ERR NOT_ATTACHED？**
A: 腳本中的 STEP 指定的 servo_id 尚未 ATTACH，需先送 ATTACH 指令。

**Q: ERR BUSY？**
A: 腳本執行中，先送 STOP 再重試。

**Q: home=0 後 Servo 停在那裡怎麼回來？**
A: 送 `STOP` 強制所有 Servo 歸位，或下一個步驟設 home=1。
