#include <Servo.h>

// ── 設定 ──────────────────────────────────
#define MAX_SERVOS      6       // 最多支援 6 顆 Servo（id 1–6）
#define MAX_STEPS       48      // 腳本最多 48 步
#define BUF_SIZE        64      // Serial 讀取緩衝區（加大給 ATTACH 指令）
#define SERIAL_BAUD     115200

#define SPD_SLOW        20      // speed=1   每度延遲 ms
#define SPD_FAST        1       // speed=100 每度延遲 ms

// ── Servo 管理 ─────────────────────────────
// id 1–6 對應 index 0–5
struct ServoSlot {
  Servo   obj;            // Servo 物件
  int16_t angle;          // 目前角度
  bool    attached;       // 是否已 ATTACH
  uint8_t pin;            // 接腳
};
ServoSlot servos[MAX_SERVOS];

// ── 腳本步驟 ──────────────────────────────
// STEP delay_ms servo_id angle speed duration_ms home
struct Step {
  uint16_t delay_ms;
  uint16_t duration_ms;
  uint8_t  sid;           // servo_id 1–6
  uint8_t  angle;
  uint8_t  speed;
  uint8_t  home;          // 0=停住 1=歸位
};
// 每個 Step 8 bytes，48 步 = 384 bytes SRAM

// ── 全域變數 ──────────────────────────────
Step    steps[MAX_STEPS];
uint8_t stepCount = 0;
uint8_t curStep   = 0;
uint8_t expSteps  = 0;
bool    running   = false;
bool    looping   = false;
bool    recving   = false;
char    buf[BUF_SIZE];

// ── 數字解析（取代 sscanf，省 ~1800B Flash）─
static char* parseU16(char *p, uint16_t &out) {
  while (*p == ' ') p++;
  uint16_t v = 0;
  while (*p >= '0' && *p <= '9') v = v * 10 + (*p++ - '0');
  out = v;
  return p;
}
static char* parseU8(char *p, uint8_t &out) {
  while (*p == ' ') p++;
  uint16_t v = 0;
  while (*p >= '0' && *p <= '9') v = v * 10 + (*p++ - '0');
  out = (uint8_t)v;
  return p;
}

// ── 輔助：servo_id 轉 index（1–6 → 0–5）─────
// 回傳 -1 表示無效或未 ATTACH
static int8_t slotOf(uint8_t sid) {
  if (sid < 1 || sid > MAX_SERVOS) return -1;
  return (int8_t)(sid - 1);
}

// ── Servo 平滑移動 ─────────────────────────
void moveServo(int8_t idx, int16_t target, uint8_t spd) {
  ServoSlot &s = servos[idx];
  target = constrain(target, 0, 180);
  spd    = constrain(spd, 1, 100);
  int     dpd = map(spd, 1, 100, SPD_SLOW, SPD_FAST);
  int16_t dir = (target > s.angle) ? 1 : -1;
  while (s.angle != target) {
    s.angle += dir;
    s.obj.write(s.angle);
    delay(dpd);
  }
}

// ── 所有已 ATTACH 的 Servo 依序歸位 ─────────
void homeAll(uint8_t spd) {
  for (uint8_t i = 0; i < MAX_SERVOS; i++) {
    if (servos[i].attached) {
      moveServo(i, 0, spd);
    }
  }
}

// ── 執行單步 ──────────────────────────────
void execStep(Step &s) {
  int8_t idx = slotOf(s.sid);

  // ① 執行前等待（分段 10ms，讓 STOP 可中斷）
  if (s.delay_ms > 0) {
    uint16_t w = 0;
    while (w < s.delay_ms) {
      delay(10);
      w += 10;
      if (!running) return;
    }
  }

  // ② idx 無效（理論上已在 STEP 解析時檢查，保險再查一次）
  if (idx < 0 || !servos[idx].attached) return;

  // ③ 移動到目標角度
  moveServo(idx, s.angle, s.speed);

  // ④ 停留
  if (s.duration_ms > 0) delay(s.duration_ms);

  // ⑤ 歸位（home=1 才執行，只歸這顆）
  if (s.home) moveServo(idx, 0, s.speed);
}

// ── 回應輔助（F() 把字串存 Flash）─────────
inline void ok(const __FlashStringHelper *s)  { Serial.println(s); }
inline void err(const __FlashStringHelper *s) { Serial.println(s); }

// ── 指令解析 ──────────────────────────────
void processCommand(char *p) {

  // PING
  if (!strcmp(p, "PING")) { ok(F("OK PONG")); return; }

  // STATUS
  if (!strcmp(p, "STATUS")) {
    if (running) {
      Serial.print(F("OK RUNNING "));
      Serial.print(curStep + 1);
      Serial.print('/');
      Serial.println(stepCount);
    } else {
      // 順便回報已 ATTACH 的 Servo 列表
      Serial.print(F("OK IDLE ATTACHED="));
      bool first = true;
      for (uint8_t i = 0; i < MAX_SERVOS; i++) {
        if (servos[i].attached) {
          if (!first) Serial.print(',');
          Serial.print(i + 1);
          first = false;
        }
      }
      if (first) Serial.print('0');  // 沒有任何 ATTACH
      Serial.println();
    }
    return;
  }

  // STOP — 停止，所有已 ATTACH 的 Servo 依序歸位
  if (!strcmp(p, "STOP")) {
    running = recving = false;
    curStep = 0;
    homeAll(80);
    ok(F("OK STOPPED"));
    return;
  }

  // ATTACH sid pin — 動態註冊 Servo
  // 例：ATTACH 1 9  → Servo 1 接在 D9
  if (!strncmp(p, "ATTACH ", 7)) {
    uint8_t sid, pin;
    char *q = p + 7;
    q = parseU8(q, sid);
    q = parseU8(q, pin);
    int8_t idx = slotOf(sid);
    if (idx < 0) { err(F("ERR INVALID_SERVO")); return; }
    if (running)  { err(F("ERR BUSY"));          return; }

    // 若已 ATTACH 先 detach
    if (servos[idx].attached) {
      servos[idx].obj.detach();
    }
    servos[idx].obj.attach(pin);
    servos[idx].pin      = pin;
    servos[idx].angle    = 0;
    servos[idx].attached = true;
    servos[idx].obj.write(0);   // 歸位
    delay(300);                 // 等 Servo 到位

    Serial.print(F("OK ATTACH "));
    Serial.print(sid);
    Serial.print(' ');
    Serial.println(pin);
    return;
  }

  // DETACH sid — 釋放 Servo
  if (!strncmp(p, "DETACH ", 7)) {
    uint8_t sid;
    parseU8(p + 7, sid);
    int8_t idx = slotOf(sid);
    if (idx < 0)              { err(F("ERR INVALID_SERVO")); return; }
    if (!servos[idx].attached){ err(F("ERR NOT_ATTACHED"));  return; }
    servos[idx].obj.detach();
    servos[idx].attached = false;
    Serial.print(F("OK DETACH "));
    Serial.println(sid);
    return;
  }

  // END
  if (!strcmp(p, "END")) {
    if (!recving)              { err(F("ERR NO_BEGIN"));      return; }
    if (stepCount != expSteps) { err(F("ERR STEP_MISMATCH")); recving = false; return; }
    recving = false;
    curStep = 0;
    running = true;
    ok(F("OK RUNNING"));
    return;
  }

  // LOOP 0/1
  if (!strncmp(p, "LOOP ", 5)) {
    looping = (p[5] == '1');
    Serial.print(F("OK LOOP "));
    Serial.println(looping ? '1' : '0');
    return;
  }

  // BEGIN n
  if (!strncmp(p, "BEGIN ", 6)) {
    if (running)                           { err(F("ERR BUSY"));     return; }
    expSteps = atoi(p + 6);
    if (!expSteps || expSteps > MAX_STEPS) { err(F("ERR OVERFLOW")); return; }
    stepCount = 0;
    recving   = true;
    ok(F("OK RECEIVING"));
    return;
  }

  // STEP delay_ms servo_id angle speed duration_ms [home]
  // home 可省略，預設 1（歸位）
  if (!strncmp(p, "STEP ", 5) && recving) {
    if (stepCount >= MAX_STEPS) { err(F("ERR OVERFLOW")); return; }

    uint16_t d, dur;
    uint8_t  sid, a, sp, h = 1;
    char *q  = p + 5;
    char *q0 = q;
    q = parseU16(q, d);
    q = parseU8 (q, sid);
    q = parseU8 (q, a);
    q = parseU8 (q, sp);
    q = parseU16(q, dur);
    if (q == q0) { err(F("ERR PARSE")); return; }

    // 檢查 servo_id 有效且已 ATTACH
    int8_t idx = slotOf(sid);
    if (idx < 0)              { err(F("ERR INVALID_SERVO")); return; }
    if (!servos[idx].attached){ err(F("ERR NOT_ATTACHED"));  return; }

    // home 欄位（可選）
    if (*q) parseU8(q, h);
    h = h ? 1 : 0;

    steps[stepCount].delay_ms    = d;
    steps[stepCount].sid         = sid;
    steps[stepCount].angle       = constrain(a,  0, 180);
    steps[stepCount].speed       = constrain(sp, 1, 100);
    steps[stepCount].duration_ms = dur;
    steps[stepCount].home        = h;
    stepCount++;
    Serial.print(F("OK STEP "));
    Serial.println(stepCount);
    return;
  }

  err(F("ERR UNKNOWN"));
}

// ── setup ──────────────────────────────────
void setup() {
  Serial.begin(SERIAL_BAUD);
  // 初始化所有 Slot 為未 ATTACH
  for (uint8_t i = 0; i < MAX_SERVOS; i++) {
    servos[i].attached = false;
    servos[i].angle    = 0;
    servos[i].pin      = 0;
  }
  ok(F("OK READY"));
}

// ── loop ───────────────────────────────────
void loop() {
  // 讀取 Serial 指令
  if (Serial.available()) {
    int len = Serial.readBytesUntil('\n', buf, BUF_SIZE - 1);
    buf[len] = '\0';
    if (len > 0 && buf[len-1] == '\r') buf[--len] = '\0';
    if (len > 0) processCommand(buf);
  }

  // 執行腳本
  if (running && stepCount > 0) {
    execStep(steps[curStep]);
    if (!running) return;
    curStep++;
    if (curStep >= stepCount) {
      if (looping) {
        curStep = 0;
        ok(F("OK LOOP_RESTART"));
      } else {
        running = false;
        curStep = 0;
        ok(F("OK DONE"));
      }
    } else {
      Serial.print(F("OK RUNNING "));
      Serial.print(curStep + 1);
      Serial.print('/');
      Serial.println(stepCount);
    }
  }
}
