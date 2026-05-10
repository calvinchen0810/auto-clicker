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

## Web UI 與 API 使用說明

### 使用步驟

1. 啟動 server：`python main.py`（或執行 EXE）
2. 開啟瀏覽器：`http://127.0.0.1:7070`
3. 選擇 COM port 並按 `CONNECT`
4. 在 Servo 管理區設定腳位並執行 `ATTACH`
5. 於單步測試或腳本編輯器執行動作

### Server 架構（詳細）

`server/` 採用 FastAPI + WebSocket + Serial 管理器三層設計：

- `main.py`：啟動入口，建立並啟動 Uvicorn（預設 `127.0.0.1:7070`）
- `server.py`：
  - 定義 REST API（例如 `/api/connect`、`/api/attach`、`/api/run`）
  - 管理 WebSocket 連線，推播狀態給前端
  - 驗證請求資料並協調執行流程
- `serial_manager.py`：
  - 封裝 PySerial 連線、送收、背景讀取執行緒
  - 維護 attach 狀態（`sid -> pin`）
  - 送出 `LOOP/BEGIN/STEP/END` 腳本指令
  - 使用 `attach_servo_and_wait` 等待 `OK ATTACH`，避免 attach 後立即 step 的競速問題
- `static/index.html`：純前端單頁介面，透過 HTTP 與 WebSocket 與後端互動

資料流：

1. Web UI 或外部程式呼叫 REST API
2. `server.py` 驗證後呼叫 `serial_manager.py`
3. `serial_manager.py` 送 Serial 指令到 Arduino
4. Arduino 回傳行資料，server 同步狀態並 WebSocket 回推前端

### Web UI 架構（詳細）

`static/index.html` 主要區塊：

- 連線控制區：掃描 COM、連線/斷線、狀態顯示
- Servo 管理區：S1-S6 pin 設定、Attach/Detach、狀態同步
- 單步測試區：即時送單一步驟
- 腳本編輯區：
  - 建立多筆步驟
  - Loop 開關
  - 匯入/匯出 JSON
  - 可輸出/匯入 `attach_cmds` 與 `servos`
  - 一鍵呼叫 `/api/run`

### API 端點總覽

| 方法 | 路徑 | 說明 |
|------|------|------|
| GET | `/api/ports` | 列出可用 COM port |
| GET | `/api/status` | 查詢狀態與 attach 清單 |
| POST | `/api/connect` | 連線 |
| POST | `/api/disconnect` | 斷線 |
| POST | `/api/attach` | 單顆 ATTACH |
| POST | `/api/detach` | 單顆 DETACH |
| POST | `/api/attach_all` | 批次 ATTACH |
| POST | `/api/detach_all` | 批次 DETACH |
| POST | `/api/run` | 執行腳本（可含 `attach_cmds`、`servos`） |
| POST | `/api/stop` | 停止 |
| POST | `/api/command` | 送出單一步驟 |
| POST | `/api/send` | 傳送原始 Serial 指令 |
| WS | `/ws` | 即時事件推送 |

### curl 使用方式（Windows）

連線：

```bash
curl.exe -X POST "http://127.0.0.1:7070/api/connect" ^
  -H "Content-Type: application/json" ^
  -d "{\"port\":\"COM3\"}"
```

執行腳本（指定 JSON 檔，與根 README 同規格）：

```bash
curl.exe -X POST http://127.0.0.1:7070/api/run -H "Content-Type: application/json" --data-binary "@servo_script_with_attach.json"
```

停止：

```bash
curl.exe -X POST "http://127.0.0.1:7070/api/stop"
```

斷線：

```bash
curl.exe -X POST "http://127.0.0.1:7070/api/disconnect"
```

### `servo_script_with_attach.json` 範例

```json
{
  "loop": false,
  "attach_cmds": [
    "ATTACH 1 9",
    "ATTACH 2 10"
  ],
  "servos": {
    "1": 9,
    "2": 10
  },
  "steps": [
    {
      "delay_ms": 200,
      "servo_id": 1,
      "angle": 90,
      "speed": 60,
      "duration_ms": 300,
      "home": 1
    }
  ]
}
```

### Python 呼叫範例

```python
import requests

BASE = "http://127.0.0.1:7070"

requests.post(f"{BASE}/api/connect", json={"port": "COM3"})

requests.post(
    f"{BASE}/api/run",
    json={
        "loop": False,
        "attach_cmds": ["ATTACH 1 9"],
        "servos": {"1": 9},
        "steps": [
            {
                "delay_ms": 1000,
                "servo_id": 1,
                "angle": 90,
                "speed": 60,
                "duration_ms": 300,
                "home": 1,
            }
        ],
    },
)
```

### WebSocket 事件

連線位址：`ws://127.0.0.1:7070/ws`

| `type` | 說明 | 主要欄位 |
|--------|------|---------|
| `status` | 狀態變更 | `state`, `port`, `attached`, `step`, `total` |
| `attached` | ATTACH/DETACH 更新 | `attached` |
| `serial` | Arduino 輸出一行 | `line` |
| `done` | 腳本執行完成 | — |
| `error` | 發生錯誤 | `message` |
