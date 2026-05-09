// servo_controller.ino
//
// Arduino Nano + Servo 自動按鍵控制器
// 透過 Serial 接收腳本指令，控制 Servo 按壓動作
//
// 接線：
//   D9  → Servo 訊號線（橘/黃）
//   5V  → Servo 電源（紅）     ← 建議外接 5V
//   GND → Servo 接地（棕/黑）
//
// Serial 鮑率：115200
// 開發工具：Arduino IDE 2.x

#include <Servo.h>

// ─────────────────────────────────────────
//  設定區（可依硬體調整）
// ─────────────────────────────────────────
#define SERVO_PIN        9      // Servo 訊號接腳
#define SERIAL_BAUD      115200 // Serial 鮑率
#define MAX_STEPS        64     // 腳本最大步數
#define SERIAL_BUF_SIZE  64     // Serial 讀取緩衝區大小

// speed 1–100 對應每度移動延遲
// speed=1   → 最慢，每度 20ms
// speed=100 → 最快，每度 1ms
#define SPEED_MIN_DELAY  20
#define SPEED_MAX_DELAY  1

// ─────────────────────────────────────────
//  資料結構
// ─────────────────────────────────────────
struct Step {
  uint16_t delay_ms;    // 執行前等待 ms
  uint16_t duration_ms; // 按壓停留 ms
  uint8_t  angle;       // 目標角度 0–180
  uint8_t  speed;       // 移動速度 1–100
};

// ─────────────────────────────────────────
//  全域變數
// ─────────────────────────────────────────
Servo   servo;
Step    steps[MAX_STEPS];
uint8_t stepCount      = 0;
uint8_t currentStep    = 0;
uint8_t expectedSteps  = 0;

bool    isRunning       = false;
bool    loopMode        = false;
bool    receivingScript = false;

int     currentAngle   = 0;   // 目前角度（smooth move 用）
char    serialBuf[SERIAL_BUF_SIZE];

// ─────────────────────────────────────────
//  Servo 平滑移動
// ─────────────────────────────────────────
void moveServo(int targetAngle, uint8_t speed) {
  speed = constrain(speed, 1, 100);
  int delayPerDegree = map(speed, 1, 100, SPEED_MIN_DELAY, SPEED_MAX_DELAY);
  int dir = (targetAngle > currentAngle) ? 1 : -1;

  while (currentAngle != targetAngle) {
    currentAngle += dir;
    servo.write(currentAngle);
    delay(delayPerDegree);
  }
}

// ─────────────────────────────────────────
//  執行單一步驟
// ─────────────────────────────────────────
void executeStep(Step &s) {
  // 1. 等待延遲（分段 10ms，讓 STOP 能即時中斷）
  if (s.delay_ms > 0) {
    uint16_t waited = 0;
    while (waited < s.delay_ms) {
      delay(10);
      waited += 10;
      if (!isRunning) return;
    }
  }

  // 2. 移動到目標角度（按下）
  moveServo(s.angle, s.speed);

  // 3. 停留
  if (s.duration_ms > 0) delay(s.duration_ms);

  // 4. 歸位（回到 0 度）
  moveServo(0, s.speed);
}

// ─────────────────────────────────────────
//  Serial 指令解析
// ─────────────────────────────────────────
void processCommand(char *line) {

  // PING — 確認連線
  if (strcmp(line, "PING") == 0) {
    Serial.println("OK PONG");
    return;
  }

  // STATUS — 查詢狀態
  if (strcmp(line, "STATUS") == 0) {
    if (isRunning) {
      Serial.print("OK RUNNING ");
      Serial.print(currentStep + 1);
      Serial.print("/");
      Serial.println(stepCount);
    } else {
      Serial.println("OK IDLE");
    }
    return;
  }

  // LOOP 0/1 — 設定循環模式
  if (strncmp(line, "LOOP ", 5) == 0) {
    loopMode = (atoi(line + 5) == 1);
    Serial.print("OK LOOP ");
    Serial.println(loopMode ? "1" : "0");
    return;
  }

  // BEGIN n — 開始接收腳本
  if (strncmp(line, "BEGIN ", 6) == 0) {
    if (isRunning) {
      Serial.println("ERR BUSY");
      return;
    }
    expectedSteps = atoi(line + 6);
    if (expectedSteps == 0 || expectedSteps > MAX_STEPS) {
      Serial.println("ERR OVERFLOW");
      return;
    }
    stepCount       = 0;
    receivingScript = true;
    Serial.println("OK RECEIVING");
    return;
  }

  // STEP delay_ms angle speed duration_ms
  if (strncmp(line, "STEP ", 5) == 0 && receivingScript) {
    if (stepCount >= MAX_STEPS) {
      Serial.println("ERR OVERFLOW");
      return;
    }
    uint16_t d, dur;
    uint8_t  a, sp;
    int parsed = sscanf(line + 5, "%u %hhu %hhu %u", &d, &a, &sp, &dur);
    if (parsed != 4) {
      Serial.println("ERR PARSE");
      return;
    }
    steps[stepCount].delay_ms    = d;
    steps[stepCount].angle       = constrain(a,  0, 180);
    steps[stepCount].speed       = constrain(sp, 1, 100);
    steps[stepCount].duration_ms = dur;
    stepCount++;
    Serial.print("OK STEP ");
    Serial.println(stepCount);
    return;
  }

  // END — 腳本接收完畢，開始執行
  if (strcmp(line, "END") == 0) {
    if (!receivingScript) {
      Serial.println("ERR NOT_RECEIVING");
      return;
    }
    if (stepCount != expectedSteps) {
      Serial.print("ERR STEP_MISMATCH expected=");
      Serial.print(expectedSteps);
      Serial.print(" got=");
      Serial.println(stepCount);
      receivingScript = false;
      return;
    }
    receivingScript = false;
    currentStep     = 0;
    isRunning       = true;
    Serial.println("OK RUNNING");
    return;
  }

  // STOP — 立即停止並歸位
  if (strcmp(line, "STOP") == 0) {
    isRunning       = false;
    receivingScript = false;
    currentStep     = 0;
    moveServo(0, 80);
    Serial.println("OK STOPPED");
    return;
  }

  Serial.println("ERR UNKNOWN");
}

// ─────────────────────────────────────────
//  setup
// ─────────────────────────────────────────
void setup() {
  Serial.begin(SERIAL_BAUD);
  servo.attach(SERVO_PIN);

  // 開機歸位
  currentAngle = 0;
  servo.write(0);
  delay(500);

  Serial.println("OK READY");
}

// ─────────────────────────────────────────
//  loop
// ─────────────────────────────────────────
void loop() {

  // 讀取 Serial 指令
  if (Serial.available()) {
    int len = Serial.readBytesUntil('\n', serialBuf, SERIAL_BUF_SIZE - 1);
    serialBuf[len] = '\0';
    // 去掉 Windows \r
    if (len > 0 && serialBuf[len - 1] == '\r') {
      serialBuf[--len] = '\0';
    }
    if (len > 0) {
      processCommand(serialBuf);
    }
  }

  // 執行腳本
  if (isRunning && stepCount > 0) {
    executeStep(steps[currentStep]);
    if (!isRunning) return;

    currentStep++;
    if (currentStep >= stepCount) {
      if (loopMode) {
        currentStep = 0;
        Serial.println("OK LOOP_RESTART");
      } else {
        isRunning   = false;
        currentStep = 0;
        Serial.println("OK DONE");
      }
    } else {
      Serial.print("OK RUNNING ");
      Serial.print(currentStep + 1);
      Serial.print("/");
      Serial.println(stepCount);
    }
  }
}
