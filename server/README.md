# Servo Controller Server

FastAPI + WebSocket HTTP Server，提供：
1. **Web UI**：瀏覽器控制 Arduino + Servo（對應 serial_tester.py 的所有功能）
2. **REST API**：外部 EXE 透過 HTTP 傳腳本控制 Arduino

---

## 快速啟動

```bash
cd server
pip install -r requirements.txt
python main.py
```

啟動後：
- Console 視窗自動縮到最小
- 瀏覽器開啟 **http://localhost:7070**

---

## 打包成 EXE（Windows）

```bash
python build.py --clean
# 輸出：dist/ServoServer.exe
```

雙擊 `ServoServer.exe`：
- Console 視窗顯示狀態後自動縮到最小
- 瀏覽器手動開啟 http://localhost:7070

---

## Web UI 功能

| 功能 | 說明 |
|------|------|
| COM port 選擇 + 連線 | 自動偵測或手動選擇 |
| 快速指令 | PING / STATUS / STOP 一鍵送出 |
| 單步測試 | 設定參數後送出，角度視覺指示器即時更新 |
| home 切換 | 1=執行完回 0°，0=停在目標角度 |
| 腳本編輯器 | 表格式編輯，拖曳排序步驟 |
| 匯入 / 匯出 JSON | 腳本以 `.json` 格式存取 |
| 循環執行 | 勾選 LOOP 或點「循環執行」 |
| Serial Monitor | WebSocket 即時串流，支援過濾 |

---

## REST API

Swagger UI：**http://localhost:7070/docs**

| 方法 | 路徑 | 說明 |
|------|------|------|
| `GET` | `/api/status` | 連線狀態 |
| `GET` | `/api/ports` | 掃描 COM port |
| `POST` | `/api/connect` | 連線 |
| `POST` | `/api/disconnect` | 斷線 |
| `POST` | `/api/run` | 執行腳本 |
| `POST` | `/api/stop` | 停止 |
| `POST` | `/api/command` | 送出單一指令 |
| `POST` | `/api/send` | 傳送原始 Serial 指令 |
| `WS` | `/ws` | WebSocket 即時推送 |

---

## 外部 EXE 呼叫範例

```python
import requests

requests.post("http://localhost:7070/api/run", json={
    "loop": False,
    "steps": [
        {"delay_ms": 2000, "angle": 90, "speed": 60, "duration_ms": 300, "home": 1},
        {"delay_ms": 1000, "angle": 90, "speed": 60, "duration_ms": 300, "home": 1},
    ]
})
```

```bash
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
    {"delay_ms": 2000, "angle": 90, "speed": 60, "duration_ms": 300, "home": 1},
    {"delay_ms": 1000, "angle": 45, "speed": 80, "duration_ms": 200, "home": 0},
    {"delay_ms": 500,  "angle": 90, "speed": 60, "duration_ms": 300, "home": 1}
  ]
}
```

| 欄位 | 範圍 | 說明 |
|------|------|------|
| `delay_ms` | 0–65535 | 執行前等待 ms |
| `angle` | 0–180 | Servo 目標角度 |
| `speed` | 1–100 | 移動速度 |
| `duration_ms` | 0–65535 | 停留 ms |
| `home` | 0 或 1（預設 1）| 執行完是否歸位 |

---

## WebSocket 事件

連線：`ws://localhost:7070/ws`

| `type` | 說明 | 欄位 |
|--------|------|------|
| `serial` | Arduino 輸出一行 | `line` |
| `status` | 狀態變更 | `state`, `port`, `step`, `total` |
| `done` | 腳本執行完畢 | — |
| `error` | 錯誤 | `message` |
