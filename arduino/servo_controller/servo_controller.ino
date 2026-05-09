#include <Servo.h>

// ── 設定 ──────────────────────────────────
#define SERVO_PIN       9
#define SERIAL_BAUD     115200
#define MAX_STEPS       48      // 最多 48 步
#define BUF_SIZE        52      // 多 4 bytes 給新增的 home 欄位

#define SPD_SLOW        20      // speed=1   每度延遲 ms
#define SPD_FAST        1       // speed=100 每度延遲 ms

// ── 資料結構 ──────────────────────────────
// STEP delay_ms angle speed duration_ms home
// home=1 → 執行完回 0°（原本行為）
// home=0 → 停在目標角度不歸位
struct Step {
  uint16_t delay_ms;
  uint16_t duration_ms;
  uint8_t  angle;
  uint8_t  speed;
  uint8_t  home;       // 新增：0=不歸位 1=歸位
};
// 每個 Step 7 bytes，48 步 = 336 bytes SRAM

// ── 全域變數 ──────────────────────────────
Servo   servo;
Step    steps[MAX_STEPS];
uint8_t stepCount = 0;
uint8_t curStep   = 0;
uint8_t expSteps  = 0;
int16_t curAngle  = 0;
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

// ── Servo 平滑移動 ─────────────────────────
void moveServo(int16_t target, uint8_t spd) {
  target = constrain(target, 0, 180);
  spd    = constrain(spd, 1, 100);
  int     dpd = map(spd, 1, 100, SPD_SLOW, SPD_FAST);
  int16_t dir = (target > curAngle) ? 1 : -1;
  while (curAngle != target) {
    curAngle += dir;
    servo.write(curAngle);
    delay(dpd);
  }
}

// ── 執行單步 ──────────────────────────────
void execStep(Step &s) {
  // ① 執行前等待（分段 10ms，讓 STOP 可中斷）
  if (s.delay_ms > 0) {
    uint16_t w = 0;
    while (w < s.delay_ms) {
      delay(10);
      w += 10;
      if (!running) return;
    }
  }

  // ② 移動到目標角度
  moveServo(s.angle, s.speed);

  // ③ 停留
  if (s.duration_ms > 0) delay(s.duration_ms);

  // ④ 歸位（home=1 才執行）
  if (s.home) moveServo(0, s.speed);
}

// ── 回應輔助 ──────────────────────────────
inline void ok(const __FlashStringHelper *s)  { Serial.println(s); }
inline void err(const __FlashStringHelper *s) { Serial.println(s); }

// ── 指令解析 ──────────────────────────────
void processCommand(char *p) {

  // PING
  if (!strcmp(p, "PING"))   { ok(F("OK PONG")); return; }

  // STATUS
  if (!strcmp(p, "STATUS")) {
    if (running) {
      Serial.print(F("OK RUNNING "));
      Serial.print(curStep + 1);
      Serial.print('/');
      Serial.println(stepCount);
    } else {
      ok(F("OK IDLE"));
    }
    return;
  }

  // STOP — 停止並強制歸位
  if (!strcmp(p, "STOP")) {
    running = recving = false;
    curStep = 0;
    moveServo(0, 80);
    ok(F("OK STOPPED"));
    return;
  }

  // END — 腳本傳完，開始執行
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

  // STEP delay_ms angle speed duration_ms home
  // home 欄位可省略，預設為 1（維持向下相容）
  if (!strncmp(p, "STEP ", 5) && recving) {
    if (stepCount >= MAX_STEPS) { err(F("ERR OVERFLOW")); return; }

    uint16_t d, dur;
    uint8_t  a, sp, h = 1;   // h 預設 1（歸位）
    char *q = p + 5;
    char *q0 = q;
    q = parseU16(q, d);
    q = parseU8 (q, a);
    q = parseU8 (q, sp);
    q = parseU16(q, dur);
    if (q == q0) { err(F("ERR PARSE")); return; }

    // home 欄位（可選）
    if (*q) parseU8(q, h);
    h = h ? 1 : 0;           // 正規化為 0 或 1

    steps[stepCount].delay_ms    = d;
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
  servo.attach(SERVO_PIN);
  servo.write(0);
  delay(500);
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
