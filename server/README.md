# Servo Controller Server

FastAPI + WebSocket HTTP Server，提供：
1. **Web UI**：瀏覽器控制 Arduino + Servo（最多 6 顆 SG90）
2. **REST API**：外部程式透過 HTTP 傳腳本控制 Arduino

---

## 環境建立

### 需求

| 項目 | 版本 |
|------|------|
| Python | 3.11 以上 |
| pip 套件 | 見 requirements.txt |

### 安裝

```bash
cd server
pip install -r requirements.txt
```

requirements.txt 內容：
```
fastapi==0.111.0
uvicorn[standard]==0.29.0
pyserial==3.5
websockets==12.0
pyinstaller==6.6.0
```

### 啟動（開發模式）

```bash
python main.py
```

啟動後：
- Console 顯示狀態後自動縮到最小
- 瀏覽器手動開啟 **http://localhost:7070**
- API 文件：http://localhost:7070/docs

---

## 打包成 EXE（Windows）

```bash
python build.py --clean
# 輸出：dist/ServoServer.exe
```

雙擊 `ServoServer.exe`：
1. Console 顯示狀態（自動縮到最小）
2. 自動偵測並連線 Arduino
3. 瀏覽器手動開啟 http://localhost:7070

---

## Web UI 使用說明

### 介面佈局

```
┌─[SERVO CTRL]── ● IDLE  COM3  [port▼][⟳][CONNECT] ── HTTP:7070 ──┐
│                                                                    │
│ ┌── Servo管理 ──┐  ┌── 單步測試 ──────┐  ┌── 執行進度 ──────────┐ │
│ │ S1 ● D9  DETACH│  │ 延遲  [  0] ms   │  │  2 / 6   LOOP ●     │ │
│ │ S2 ○ [10]ATTACH│  │ ServoID[ 1]      │  │  ████████░░  33%    │ │
│ │ S3 ○ [11]ATTACH│  │ 角度  [ 90] °  ◜ │  ├──── 執行控制 ──────┤ │
│ │ S4 ○ [ 6]ATTACH│  │ 速度  [ 60]      │  │ [▶ RUN][↺ LOOP]    │ │
│ │ S5 ○ [ 5]ATTACH│  │ 停留  [300] ms   │  │ [■■■■■ STOP ■■■■■] │ │
│ │ S6 ○ [ 3]ATTACH│  │ 歸位[1 回0°][0停] │  ├──── Serial Monitor ┤ │
│ │[全部ATTACH][全部]│  │   ◜  home=1     │  │ ← OK READY         │ │
│ ├── 快速指令 ───┤  │ [▶ 送出][預覽]  │  │ → ATTACH 1 9       │ │
│ │[PING][STATUS][STOP]│  └──────────────────┘  │ ← OK ATTACH 1 9    │ │
│ └────────────────┘                             │ → BEGIN 3          │ │
│                    ┌── 腳本編輯器 ─────────┐  │ ← OK RUNNING 1/3   │ │
│                    │[載入][匯入][匯出]☐循環 │  │                    │ │
│                    │ DELAY  SID ANGLE SPD HOLD│  │ >> [手動輸入] [送出]│ │
│                    │  1000   1   90   60  300 │  └────────────────────┘ │
│                    │  1000   2   90   60  300 │                          │
│                    │[＋ ADD STEP]             │                          │
│                    └───────────────────────────┘                         │
└────────────────────────────────────────────────────────────────────────┘
```

### 連線步驟

1. 插入 Arduino Nano（USB）
2. 瀏覽器開啟 http://localhost:7070
3. 選擇 COM port（⭐ 表示可能是 Arduino）或留空自動偵測
4. 點擊 **CONNECT**
5. 狀態燈變綠色、顯示 `IDLE` 表示連線成功

### Servo 管理區

每顆 Servo 一列：

| 元素 | 說明 |
|------|------|
| `S1`–`S6` | Servo 編號 |
| `●` 狀態燈 | 綠色=已 ATTACH，灰色=未 ATTACH |
| 腳位輸入框 | 設定接哪個 Arduino Pin（未 ATTACH 時可編輯）|
| [ATTACH] | 送出 `ATTACH sid pin`，Servo 歸位到 0° |
| [DETACH] | 送出 `DETACH sid`，釋放 Servo |
| [全部 ATTACH] | 批次 ATTACH 所有 6 顆（使用各列設定的腳位）|
| [全部 DETACH] | 批次 DETACH 所有已連接的 Servo |

**預設腳位：** S1=D9, S2=D10, S3=D11, S4=D6, S5=D5, S6=D3

### 單步測試

1. 設定延遲、Servo ID（橘色）、角度、速度、停留時間
2. 選擇歸位模式：`1 回 0°` 或 `0 停住`
3. 角度指示器即時顯示目標角度
4. 點擊 **[▶ 送出單步]** 執行
   - 若該 Servo 未 ATTACH，會彈出確認對話框詢問是否先 ATTACH

### 腳本編輯器

| 功能 | 說明 |
|------|------|
| 表格編輯 | 直接點擊儲存格修改數值 |
| 拖曳排序 | 拖曳最左側 `⠿` 符號重排步驟 |
| SID 欄位 | 橘色，指定每步使用哪顆 Servo |
| 載入範例 | 預載 3 步驟示範腳本 |
| 匯入 JSON | 從檔案載入腳本 |
| 匯出 JSON | 儲存腳本為 .json 檔 |
| 循環勾選 | 腳本結束後重新執行 |

---

## REST API 文件

### 端點總覽

| 方法 | 路徑 | 說明 |
|------|------|------|
| GET | `/api/ports` | 列出可用 COM port |
| GET | `/api/status` | 查詢狀態 + 已 ATTACH 清單 |
| POST | `/api/connect` | 連線 |
| POST | `/api/disconnect` | 斷線 |
| POST | `/api/attach` | 單顆 ATTACH |
| POST | `/api/detach` | 單顆 DETACH |
| POST | `/api/attach_all` | 批次 ATTACH |
| POST | `/api/detach_all` | 批次 DETACH |
| POST | `/api/run` | 執行腳本 |
| POST | `/api/stop` | 停止 |
| POST | `/api/command` | 送出單一步驟 |
| POST | `/api/send` | 傳送原始 Serial 指令 |
| WS | `/ws` | WebSocket 即時推送 |

### API 呼叫範例

**Python（外部 EXE 整合）：**
```python
import requests

BASE = "http://localhost:7070"

# 1. 連線
requests.post(f"{BASE}/api/connect", json={"port": "COM3"})

# 2. ATTACH Servo
requests.post(f"{BASE}/api/attach", json={"sid": 1, "pin": 9})
requests.post(f"{BASE}/api/attach", json={"sid": 2, "pin": 10})

# 3. 執行腳本
requests.post(f"{BASE}/api/run", json={
    "loop": False,
    "steps": [
        {"delay_ms": 1000, "servo_id": 1, "angle": 90,
         "speed": 60, "duration_ms": 300, "home": 1},
        {"delay_ms": 500,  "servo_id": 2, "angle": 90,
         "speed": 60, "duration_ms": 300, "home": 1},
    ]
})

# 4. 查詢狀態
status = requests.get(f"{BASE}/api/status").json()
# {"state": "running", "port": "COM3", "attached": {"1": 9, "2": 10}}
```

**curl：**
```bash
# ATTACH
curl -X POST http://localhost:7070/api/attach \
  -H "Content-Type: application/json" \
  -d '{"sid": 1, "pin": 9}'

# 批次 ATTACH
curl -X POST http://localhost:7070/api/attach_all \
  -H "Content-Type: application/json" \
  -d '{"servos": {"1": 9, "2": 10, "3": 11}}'

# 執行腳本
curl -X POST http://localhost:7070/api/run \
  -H "Content-Type: application/json" \
  -d @script.json
```

---

## JSON 腳本格式

```json
{
  "loop": false,
  "steps": [
    {
      "delay_ms":    1000,
      "servo_id":    1,
      "angle":       90,
      "speed":       60,
      "duration_ms": 300,
      "home":        1
    },
    {
      "delay_ms":    500,
      "servo_id":    2,
      "angle":       90,
      "speed":       60,
      "duration_ms": 300,
      "home":        0
    }
  ]
}
```

| 欄位 | 範圍 | 說明 |
|------|------|------|
| `delay_ms` | 0–65535 | 執行前等待 ms |
| `servo_id` | 1–6 | 要動哪顆 Servo（需已 ATTACH）|
| `angle` | 0–180 | 目標角度 |
| `speed` | 1–100 | 移動速度 |
| `duration_ms` | 0–65535 | 停留 ms |
| `home` | 0 或 1（預設 1）| 執行完是否歸位 |

---

## WebSocket 事件

連線：`ws://localhost:7070/ws`

### Server → Browser

| `type` | 說明 | 主要欄位 |
|--------|------|---------|
| `status` | 狀態變更 | `state`, `port`, `attached`, `step`, `total` |
| `attached` | ATTACH/DETACH 更新 | `attached` {sid: pin} |
| `serial` | Arduino 輸出一行 | `line` |
| `done` | 腳本執行完畢 | — |
| `error` | 發生錯誤 | `message` |

### `attached` 欄位格式

```json
{"1": 9, "2": 10, "3": 11}
```
key=servo_id，value=pin。

### JavaScript 範例

```js
const ws = new WebSocket('ws://localhost:7070/ws');
ws.onmessage = (e) => {
  const msg = JSON.parse(e.data);
  if (msg.type === 'attached') {
    console.log('已 ATTACH：', msg.attached);
    // {"1": 9, "2": 10}
  }
  if (msg.type === 'done') {
    console.log('腳本執行完畢');
  }
};
```
