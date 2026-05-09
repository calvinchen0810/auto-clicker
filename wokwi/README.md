# Wokwi 模擬器使用說明

不需要實體 Arduino，在瀏覽器直接測試程式與 Servo 行為。

---

## 快速開始

### Step 1：開啟 Wokwi

前往 https://wokwi.com → 點右上角 **New Project** → 選 **Arduino Nano**

### Step 2：貼上程式碼

將 `../arduino/servo_controller/servo_controller.ino` 內容全部貼入編輯器。

### Step 3：設定電路圖

點左側 **diagram.json** 分頁，將本目錄的 `diagram.json` 內容全部貼入取代。

電路會自動出現：
```
Arduino Nano D9  ── Servo 訊號（綠）
Arduino Nano 5V  ── Servo 電源（紅）
Arduino Nano GND ── Servo 接地（黑）
```

### Step 4：執行模擬

點綠色 **▶ Play** 按鈕，Serial Monitor 出現：
```
OK READY
```

---

## Serial Monitor 操作

Wokwi Serial Monitor 輸入框在畫面下方，輸入指令後按 **Enter** 送出。

### 基本測試順序

```
# 1. 確認連線
PING
→ OK PONG

# 2. 查詢狀態
STATUS
→ OK IDLE

# 3. 單步測試（home=1，執行完回 0°）
LOOP 0
BEGIN 1
STEP 1000 90 60 300 1
END

# 4. 單步測試（home=0，停在 90°）
LOOP 0
BEGIN 1
STEP 1000 90 60 300 0
END

# 5. 強制歸位
STOP
→ OK STOPPED
```

### 完整範例：按 3 次自動歸位

```
LOOP 0
BEGIN 3
STEP 2000 90 60 300 1
STEP 1000 90 60 300 1
STEP 1000 90 60 300 1
END
```

### 連續移動不歸位（home=0），最後才回 0°

```
LOOP 0
BEGIN 3
STEP 0 45 80 200 0
STEP 0 90 80 200 0
STEP 0 135 80 300 1
END
```

### 循環模式

```
LOOP 1
BEGIN 2
STEP 500 90 80 200 1
STEP 500 45 80 200 1
END
```
Servo 持續來回，直到送出 `STOP`。

> ⚠️ Wokwi 模擬時間比真實硬體慢，建議將 delay_ms 縮小測試。

---

## STEP 指令格式

```
STEP delay_ms angle speed duration_ms [home]
```

| 參數 | 範圍 | 說明 |
|------|------|------|
| `delay_ms` | 0–65535 | 執行前等待毫秒 |
| `angle` | 0–180 | Servo 目標角度 |
| `speed` | 1–100 | 移動速度（100=最快）|
| `duration_ms` | 0–65535 | 到達後停留毫秒 |
| `home` | 0 或 1（**可省略，預設 1**）| 執行完是否歸位 |

| `home` | 行為 |
|--------|------|
| `1`（預設）| 執行完自動回到 0° |
| `0` | 停在目標角度 |

---

## Serial 指令速查

| 指令 | 說明 | 回應 |
|------|------|------|
| `PING` | 確認連線 | `OK PONG` |
| `STATUS` | 查詢狀態 | `OK IDLE` / `OK RUNNING n/total` |
| `LOOP 0/1` | 設定循環 | `OK LOOP 0/1` |
| `BEGIN n` | 開始傳腳本 | `OK RECEIVING` |
| `STEP ...` | 新增步驟 | `OK STEP n` |
| `END` | 腳本傳完執行 | `OK RUNNING` |
| `STOP` | 立即停止並歸位 | `OK STOPPED` |

## Arduino 回應說明

| 回應 | 說明 |
|------|------|
| `OK READY` | 開機完成 |
| `OK PONG` | PING 回應 |
| `OK IDLE` | 閒置中 |
| `OK RECEIVING` | 開始接收腳本 |
| `OK STEP n` | 收到第 n 步 |
| `OK RUNNING` | 腳本開始執行 |
| `OK RUNNING n/total` | 執行中進度 |
| `OK LOOP_RESTART` | 循環重新開始 |
| `OK DONE` | 執行完畢 |
| `OK STOPPED` | 已停止並歸位 |
| `ERR BUSY` | 執行中無法接收新腳本 |
| `ERR OVERFLOW` | 步數超過上限 48 |
| `ERR PARSE` | 指令格式錯誤 |
| `ERR STEP_MISMATCH` | 實際步數與 BEGIN 宣告不符 |
| `ERR NO_BEGIN` | 收到 END 但未先執行 BEGIN |
| `ERR UNKNOWN` | 未知指令 |
