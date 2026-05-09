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
Arduino Nano D9 ── Servo 訊號（橘）
Arduino Nano 5V ── Servo 電源（紅）
Arduino Nano GND── Servo 接地（黑）
```

### Step 4：執行模擬

點綠色 **▶ Play** 按鈕，Serial Monitor 出現：
```
OK READY
```
表示模擬成功啟動。

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

# 3. 測試單步動作（2秒後 Servo 動）
LOOP 0
BEGIN 2
STEP 2000 90 60 300
STEP 0 0 60 0
END
→ OK LOOP 0
→ OK RECEIVING
→ OK STEP 1
→ OK STEP 2
→ OK RUNNING
→ OK RUNNING 1/2   （Servo 轉到 90°）
→ OK RUNNING 2/2   （Servo 回到 0°）
→ OK DONE

# 4. 緊急停止
STOP
→ OK STOPPED
```

### 完整範例：10秒後按3次

```
LOOP 0
BEGIN 6
STEP 10000 90 60 300
STEP 0 0 60 0
STEP 3000 90 60 300
STEP 0 0 60 0
STEP 3000 90 60 300
STEP 0 0 60 0
END
```

> ⚠️ Wokwi 模擬時間比真實硬體慢，10000ms 延遲會跑比較久，可改小數字測試。

### 循環模式測試

```
LOOP 1
BEGIN 2
STEP 1000 90 80 200
STEP 0 0 80 0
END
```
Servo 會持續來回，直到輸入：
```
STOP
```

---

## Serial 指令速查

| 指令 | 格式 | 說明 |
|------|------|------|
| PING | `PING` | 確認連線 |
| STATUS | `STATUS` | 查詢狀態 |
| LOOP | `LOOP 0` 或 `LOOP 1` | 設定循環 |
| BEGIN | `BEGIN n` | 開始傳腳本，n=步數 |
| STEP | `STEP delay_ms angle speed duration_ms` | 新增步驟 |
| END | `END` | 腳本傳完，開始執行 |
| STOP | `STOP` | 立即停止歸位 |

### STEP 參數範圍

| 參數 | 範圍 | 說明 |
|------|------|------|
| delay_ms | 0–65535 | 執行前等待毫秒 |
| angle | 0–180 | 按壓目標角度 |
| speed | 1–100 | 移動速度（100=最快） |
| duration_ms | 0–65535 | 停留毫秒 |

---

## Arduino 回應說明

| 回應 | 說明 |
|------|------|
| `OK READY` | 開機完成 |
| `OK PONG` | PING 回應 |
| `OK IDLE` | 閒置中 |
| `OK RECEIVING` | 開始接收腳本 |
| `OK STEP n` | 收到第 n 步 |
| `OK RUNNING` | 腳本開始執行 |
| `OK RUNNING n/total` | 執行中，進度 |
| `OK LOOP_RESTART` | 循環重新開始 |
| `OK DONE` | 執行完畢 |
| `OK STOPPED` | 已停止 |
| `ERR BUSY` | 執行中，無法接收新腳本 |
| `ERR OVERFLOW` | 步數超過上限 64 |
| `ERR PARSE` | 指令格式錯誤 |
| `ERR STEP_MISMATCH` | 實際步數與 BEGIN 宣告不符 |
| `ERR UNKNOWN` | 未知指令 |
