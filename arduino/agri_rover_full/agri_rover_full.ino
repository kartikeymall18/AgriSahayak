/*
  AgriSahayak rover - FULL firmware for Arduino Uno R3
  ----------------------------------------------------------------------------------------------
  Parts used: L298N + 4 gear motors, capacitive soil sensor, DHT11, HC-SR04 ultrasonic, IR sensor,
              SG90 servo, water pump (through a relay or MOSFET module), 16x2 LCD with I2C backpack.
  Libraries: only the ones that come with the Arduino IDE (Servo, Wire, EEPROM). Nothing to install.
  Serial: 9600 baud, one command per line, one answer per line.

  PIN MAP (the wiring guide comes next round; the code only needs these numbers)
    D0 D1   USB serial (do not use)
    D2      DHT11 data
    D3      IR sensor (digital)               <- table-edge detector, looks DOWN at the table
    D4      pump relay / MOSFET input
    D5      L298N ENA  (left speed, PWM)      D7  IN1   D8  IN2   (left motors)
    D6      L298N ENB  (right speed, PWM)     D9  IN3   D10 IN4   (right motors)
    D11     SG90 servo signal                 <- carries the ultrasonic sensor for the 3-way scan
    D12     ultrasonic TRIG                   D13 ultrasonic ECHO
    A0      capacitive soil sensor (analog)
    A4 A5   I2C SDA / SCL for the LCD
    A1 A2 A3 spare

  COMMANDS (tablet or serial monitor, end with Enter)
    F B L R S      forward, back, spin left, spin right, stop
    V<0-255>       motor speed, e.g. V150
    P<1-10>        run the pump for that many seconds        Q   pump off
    W0 / W1        automatic watering off / on (waters when the soil stays dry)
    A<0-180>       servo angle                               N   scan left, centre, right
    I0 / I1        obstacle + table-edge interlock off / on (default ON)
    K0 / K1        calibrate soil sensor: K0 with sensor in dry air, K1 with sensor in water (saved)
    C              print raw soil reading                    ?   print all values once
    H              ping (answers PONG)                       X   emergency stop of everything

  OUTPUT LINES
    SOIL,<percent>   every second                    ENV,<temp C>,<humidity %>   every 2.5 s (ENV,ERR if the DHT11 fails)
    DIST,<cm>        every second (-1 = no echo)     EDGE,<0|1>   1 = table edge seen (on change and every 2 s)
    PUMP,<0|1>       on change                       BLOCK,<OBSTACLE|EDGE>   forward movement was stopped or refused
    SCAN,<left>,<centre>,<right>  in cm               STAT,...   answer to "?"
    READY,FULL,1     after start-up                  OK,<what>  / ERR,<why>   answers to commands

  SAFETY RULES BUILT IN
    - Motors stop by themselves if no drive command arrives for 700 ms (the tablet repeats commands).
    - Forward is stopped when something is closer than OBST_STOP_CM or the IR sensor sees the table edge.
    - The pump runs at most 10 s per start, waits 5 s between starts, and at most 60 s in any hour.
    - Everything is OFF at power-up. X switches everything off at once.
*/
#include <Servo.h>
#include <Wire.h>
#include <EEPROM.h>

// ------------------------------------------------------------------ pins
const uint8_t PIN_DHT = 2, PIN_IR = 3, PIN_PUMP = 4, ENA = 5, ENB = 6, IN1 = 7, IN2 = 8, IN3 = 9, IN4 = 10;
const uint8_t PIN_SERVO = 11, PIN_TRIG = 12, PIN_ECHO = 13, PIN_SOIL = A0;

// ------------------------------------------------------------------ settings you may change
#define USE_LCD 1                         // 0 = no LCD connected
#define PUMP_ACTIVE_LOW 0                 // 1 if your relay module switches ON with a LOW signal
#define EDGE_WHEN_HIGH 1                  // IR module output that means "no table below" (most modules: HIGH)
// NOTE: the IR pin has its pull-up ON. With NO IR sensor connected it reads HIGH = "edge", so forward is refused (fail-safe).
//       For bench tests without the sensor send I0 (interlock off) and I1 again before a real run.
const uint16_t OBST_STOP_CM = 15;         // stop going forward when closer than this
const uint16_t CMD_TIMEOUT_MS = 700;
const uint8_t  PUMP_MAX_SEC = 10;
const uint16_t PUMP_COOLDOWN_MS = 5000;
const uint16_t PUMP_BUDGET_SEC_PER_HOUR = 60;
const uint8_t  AUTO_DRY_PCT = 30;         // automatic watering starts below this soil %
const uint8_t  AUTO_PUMP_SEC = 3;
const uint32_t AUTO_WAIT_MS = 30000UL;    // after an automatic watering, wait this long for the water to soak in
const uint8_t  SERVO_LEFT = 150, SERVO_CENTRE = 90, SERVO_RIGHT = 30;

// ------------------------------------------------------------------ state
Servo servo;
uint8_t speedPwm = 150;
char moving = 'S';
uint32_t lastCmd = 0;
bool safetyOn = true;

int airVal = 520, waterVal = 260;          // soil calibration (raw readings), saved in EEPROM
struct Calib { uint16_t magic; int16_t air; int16_t water; };
const uint16_t CALIB_MAGIC = 0xA6A1;

int soilPct = 0;
int tempC = -99, humPct = -1; bool dhtOk = false;
int distCm = -1; uint8_t closeCount = 0; bool obstacle = false;
uint8_t edgeCount = 0; bool edge = false, lastEdgeSent = false;

bool pumpOn = false; uint32_t pumpOffAt = 0, pumpLastOff = 0; uint32_t budgetStart = 0; uint16_t budgetUsedSec = 0, pumpStartedSec = 0; uint32_t pumpStartMs = 0;
bool autoWater = false; uint32_t autoNextAt = 0, dryFor = 0, lastDryCheck = 0;

uint32_t servoDetachAt = 0; int servoAngle = SERVO_CENTRE;
uint8_t scanStep = 0; uint32_t scanNext = 0; int scanVal[3];

uint32_t tSoil = 0, tDist = 0, tEnv = 0, tEdgeSend = 0, tLcd = 0, tEdgeRead = 0, tObst = 0;
bool blockSent = false;

char buf[26]; uint8_t blen = 0;

// ------------------------------------------------------------------ motors
void side(uint8_t a, uint8_t b, uint8_t en, int dir) {
  if (dir > 0)      { digitalWrite(a, HIGH); digitalWrite(b, LOW);  analogWrite(en, speedPwm); }
  else if (dir < 0) { digitalWrite(a, LOW);  digitalWrite(b, HIGH); analogWrite(en, speedPwm); }
  else              { digitalWrite(a, LOW);  digitalWrite(b, LOW);  analogWrite(en, 0); }
}
void drive(char c) {
  moving = c;
  if (c == 'F')      { side(IN1, IN2, ENA, 1);  side(IN3, IN4, ENB, 1); }
  else if (c == 'B') { side(IN1, IN2, ENA, -1); side(IN3, IN4, ENB, -1); }
  else if (c == 'L') { side(IN1, IN2, ENA, -1); side(IN3, IN4, ENB, 1); }
  else if (c == 'R') { side(IN1, IN2, ENA, 1);  side(IN3, IN4, ENB, -1); }
  else               { side(IN1, IN2, ENA, 0);  side(IN3, IN4, ENB, 0); moving = 'S'; }
}

// ------------------------------------------------------------------ pump
void pumpWrite(bool on) {
#if PUMP_ACTIVE_LOW
  digitalWrite(PIN_PUMP, on ? LOW : HIGH);
#else
  digitalWrite(PIN_PUMP, on ? HIGH : LOW);
#endif
}
void pumpStop() {
  if (!pumpOn) return;
  pumpWrite(false); pumpOn = false; pumpLastOff = millis();
  uint16_t ran = (millis() - pumpStartMs + 500) / 1000; budgetUsedSec += ran;
  Serial.println(F("PUMP,0"));
}
bool pumpStart(uint8_t sec) {
  uint32_t now = millis();
  if (now - budgetStart > 3600000UL) { budgetStart = now; budgetUsedSec = 0; }
  if (sec < 1) { sec = 1; }
  if (sec > PUMP_MAX_SEC) { sec = PUMP_MAX_SEC; }
  if (pumpOn)                                         { Serial.println(F("ERR,PUMP_BUSY")); return false; }
  if (pumpLastOff && now - pumpLastOff < PUMP_COOLDOWN_MS) { Serial.println(F("ERR,PUMP_COOLDOWN")); return false; }
  if (budgetUsedSec + sec > PUMP_BUDGET_SEC_PER_HOUR) { Serial.println(F("ERR,PUMP_HOUR_LIMIT")); return false; }
  pumpWrite(true); pumpOn = true; pumpStartMs = now; pumpOffAt = now + (uint32_t)sec * 1000UL;
  Serial.println(F("PUMP,1")); return true;
}

// ------------------------------------------------------------------ servo
void servoGo(int a) {
  if (a < 0) { a = 0; }
  if (a > 180) { a = 180; }
  if (!servo.attached()) servo.attach(PIN_SERVO);
  servo.write(a); servoAngle = a; servoDetachAt = millis() + 700;
}

// ------------------------------------------------------------------ sensors
int readRawSoil() { long s = 0; for (uint8_t i = 0; i < 10; i++) { s += analogRead(PIN_SOIL); delay(2); } return (int)(s / 10); }
int toPct(int raw) {
  if (airVal == waterVal) return 0;
  long p = map(raw, airVal, waterVal, 0, 100);       // capacitive sensor: lower reading = wetter
  if (p < 0) { p = 0; }
  if (p > 100) { p = 100; }
  return (int)p;
}
int readDistance() {
  digitalWrite(PIN_TRIG, LOW); delayMicroseconds(3);
  digitalWrite(PIN_TRIG, HIGH); delayMicroseconds(10); digitalWrite(PIN_TRIG, LOW);
  unsigned long us = pulseIn(PIN_ECHO, HIGH, 25000UL);
  if (us == 0) return -1;
  int cm = (int)(us / 58UL); return (cm < 2 || cm > 400) ? -1 : cm;
}
int medianDistance() {                                // 3 readings, middle value, used by the scan
  int v[3]; for (uint8_t i = 0; i < 3; i++) { v[i] = readDistance(); delay(30); }
  for (uint8_t i = 0; i < 2; i++) for (uint8_t j = 0; j < 2 - i; j++) if (v[j] > v[j + 1]) { int t = v[j]; v[j] = v[j + 1]; v[j + 1] = t; }
  return v[1];
}
uint16_t pulseLen(bool level, uint16_t maxUs) {
  uint32_t st = micros(); while (digitalRead(PIN_DHT) == level) { if (micros() - st > maxUs) return 0; } return (uint16_t)(micros() - st);
}
bool readDHT11() {                                    // DHT11 read without any library
  uint8_t d[5] = {0, 0, 0, 0, 0};
  pinMode(PIN_DHT, OUTPUT); digitalWrite(PIN_DHT, LOW); delay(20);
  digitalWrite(PIN_DHT, HIGH); delayMicroseconds(30); pinMode(PIN_DHT, INPUT_PULLUP);
  if (!pulseLen(HIGH, 120)) return false;             // wait for the sensor to pull low
  if (!pulseLen(LOW, 120))  return false;             // 80 us low
  if (!pulseLen(HIGH, 120)) return false;             // 80 us high
  for (uint8_t i = 0; i < 40; i++) {
    if (!pulseLen(LOW, 100)) return false;            // ~50 us low
    uint16_t h = pulseLen(HIGH, 120); if (!h) return false;
    d[i / 8] <<= 1; if (h > 40) d[i / 8] |= 1;        // long high = 1
  }
  if (((d[0] + d[1] + d[2] + d[3]) & 0xFF) != d[4]) return false;
  humPct = d[0]; tempC = d[2]; return true;
}

// ------------------------------------------------------------------ LCD (16x2 with PCF8574 I2C backpack, no library)
#if USE_LCD
uint8_t lcdAddr = 0; char lcdLine[2][17];
void lcdRaw(uint8_t v) { Wire.beginTransmission(lcdAddr); Wire.write(v | 0x08); Wire.endTransmission(); }   // 0x08 = backlight
void lcdNib(uint8_t n, bool rs) { uint8_t b = (n << 4) | (rs ? 1 : 0); lcdRaw(b | 0x04); delayMicroseconds(2); lcdRaw(b & ~0x04); delayMicroseconds(60); }
void lcdSend(uint8_t v, bool rs) { lcdNib(v >> 4, rs); lcdNib(v & 0x0F, rs); }
void lcdInit() {
  Wire.begin();
  uint8_t cand[2] = {0x27, 0x3F};
  for (uint8_t i = 0; i < 2 && !lcdAddr; i++) { Wire.beginTransmission(cand[i]); if (Wire.endTransmission() == 0) lcdAddr = cand[i]; }
  if (!lcdAddr) return;
  delay(50); lcdNib(0x3, false); delay(5); lcdNib(0x3, false); delayMicroseconds(150); lcdNib(0x3, false); lcdNib(0x2, false);
  lcdSend(0x28, false); lcdSend(0x0C, false); lcdSend(0x06, false); lcdSend(0x01, false); delay(3);
  for (uint8_t r = 0; r < 2; r++) { memset(lcdLine[r], ' ', 16); lcdLine[r][16] = 0; }
}
void lcdShow(uint8_t row, const char* s) {            // writes only when the text changed
  if (!lcdAddr) return;
  char t[17]; uint8_t i = 0; while (i < 16 && s[i]) { t[i] = s[i]; i++; } while (i < 16) t[i++] = ' '; t[16] = 0;
  if (memcmp(t, lcdLine[row], 16) == 0) return;
  memcpy(lcdLine[row], t, 17);
  lcdSend(0x80 | (row ? 0x40 : 0x00), false);
  for (uint8_t k = 0; k < 16; k++) lcdSend((uint8_t)t[k], true);
}
#else
void lcdInit() {}
void lcdShow(uint8_t, const char*) {}
#endif

// ------------------------------------------------------------------ safety
bool frontBlocked(const __FlashStringHelper** why) {
  if (!safetyOn) return false;
  if (edge)     { *why = F("EDGE");     return true; }
  if (obstacle) { *why = F("OBSTACLE"); return true; }
  return false;
}
void emergencyStop() { drive('S'); pumpStop(); autoWater = false; scanStep = 0; }

// ------------------------------------------------------------------ commands
void printStat() {
  Serial.print(F("STAT,")); Serial.print(soilPct); Serial.print(','); Serial.print(dhtOk ? tempC : -99); Serial.print(',');
  Serial.print(dhtOk ? humPct : -1); Serial.print(','); Serial.print(distCm); Serial.print(','); Serial.print(edge);
  Serial.print(','); Serial.print(pumpOn); Serial.print(','); Serial.print(servoAngle); Serial.print(',');
  Serial.print(autoWater); Serial.print(','); Serial.println(safetyOn);
}
void handle(char* s) {
  while (*s == ' ') s++;
  if (!*s) return;
  char c = toupper(*s); int n = atoi(s + 1);
  switch (c) {
    case 'F': {
      const __FlashStringHelper* why;
      if (scanStep) { Serial.println(F("ERR,SCANNING")); break; }
      if (frontBlocked(&why)) { drive('S'); if (!blockSent) { Serial.print(F("BLOCK,")); Serial.println(why); blockSent = true; } }
      else { drive('F'); lastCmd = millis(); }
      break; }
    case 'B': case 'L': case 'R': if (scanStep) { Serial.println(F("ERR,SCANNING")); break; } drive(c); lastCmd = millis(); break;
    case 'S': drive('S'); lastCmd = millis(); break;
    case 'V': speedPwm = (uint8_t)constrain(n, 0, 255); if (moving != 'S') drive(moving); break;
    case 'P': if (pumpStart((uint8_t)constrain(n, 1, PUMP_MAX_SEC))) Serial.println(F("OK,PUMP")); break;
    case 'Q': pumpStop(); Serial.println(F("OK,PUMP_OFF")); break;
    case 'W': autoWater = (n != 0); dryFor = 0; autoNextAt = 0; Serial.println(autoWater ? F("OK,AUTOWATER_ON") : F("OK,AUTOWATER_OFF")); break;
    case 'A': servoGo(constrain(n, 0, 180)); Serial.print(F("OK,SERVO,")); Serial.println(servoAngle); break;
    case 'N': if (moving != 'S') { Serial.println(F("ERR,MOVING")); break; } scanStep = 1; scanNext = 0; Serial.println(F("OK,SCAN")); break;
    case 'I': safetyOn = (n != 0); Serial.println(safetyOn ? F("OK,SAFETY_ON") : F("OK,SAFETY_OFF")); break;
    case 'K': {
      int raw = readRawSoil();
      if (n == 0) airVal = raw; else if (n == 1) waterVal = raw; else { Serial.println(F("ERR,K0_OR_K1")); break; }
      Calib k = {CALIB_MAGIC, (int16_t)airVal, (int16_t)waterVal}; EEPROM.put(0, k);
      Serial.print(F("OK,CAL,")); Serial.print(airVal); Serial.print(','); Serial.println(waterVal); break; }
    case 'C': Serial.print(F("RAW,")); Serial.println(readRawSoil()); break;
    case '?': printStat(); break;
    case 'H': Serial.println(F("PONG")); break;
    case 'X': emergencyStop(); Serial.println(F("OK,ALL_OFF")); break;
    default: Serial.println(F("ERR,UNKNOWN"));
  }
}

// ------------------------------------------------------------------ setup / loop
void setup() {
  pinMode(ENA, OUTPUT); pinMode(ENB, OUTPUT); pinMode(IN1, OUTPUT); pinMode(IN2, OUTPUT); pinMode(IN3, OUTPUT); pinMode(IN4, OUTPUT);
  pinMode(PIN_PUMP, OUTPUT); pumpWrite(false);
  pinMode(PIN_TRIG, OUTPUT); pinMode(PIN_ECHO, INPUT); pinMode(PIN_IR, INPUT_PULLUP); pinMode(PIN_DHT, INPUT_PULLUP);
  drive('S');
  Calib k; EEPROM.get(0, k); if (k.magic == CALIB_MAGIC && k.air != k.water) { airVal = k.air; waterVal = k.water; }
  Serial.begin(9600);
  lcdInit(); lcdShow(0, "AgriSahayak"); lcdShow(1, "Starting...");
  budgetStart = millis();
  soilPct = toPct(readRawSoil());
  Serial.println(F("READY,FULL,1"));
}

void loop() {
  uint32_t now = millis();

  // ---- serial commands
  while (Serial.available() > 0) {
    char ch = (char)Serial.read();
    if (ch == '\n' || ch == '\r') { buf[blen] = 0; if (blen) handle(buf); blen = 0; }
    else if (blen < sizeof(buf) - 1) buf[blen++] = ch;
  }

  // ---- table-edge sensor, read often, needs 3 equal reads in a row
  if (now - tEdgeRead >= 20) {
    tEdgeRead = now;
    bool seen = (digitalRead(PIN_IR) == (EDGE_WHEN_HIGH ? HIGH : LOW));
    if (seen != edge) { if (++edgeCount >= 3) { edge = seen; edgeCount = 0; } } else edgeCount = 0;
  }
  // ---- distance, about 8 times a second (needs 2 close readings in a row)
  if (now - tObst >= 120 && !scanStep) {
    tObst = now; int d = readDistance();
    if (d > 0) distCm = d; else distCm = -1;
    if (d > 0 && d < (int)OBST_STOP_CM) { if (closeCount < 3) closeCount++; } else closeCount = 0;
    obstacle = (closeCount >= 2);
  }

  // ---- interlock: stop forward movement at once
  {
    const __FlashStringHelper* why;
    bool fb = frontBlocked(&why);
    if (!fb) blockSent = false;
    if (moving == 'F' && fb) { drive('S'); if (!blockSent) { Serial.print(F("BLOCK,")); Serial.println(why); blockSent = true; } }
  }
  // ---- motor watchdog
  if (moving != 'S' && now - lastCmd > CMD_TIMEOUT_MS) drive('S');

  // ---- pump timer
  if (pumpOn && (int32_t)(now - pumpOffAt) >= 0) pumpStop();

  // ---- automatic watering
  if (autoWater && !pumpOn && now - lastDryCheck >= 1000) {
    lastDryCheck = now;
    if (soilPct < AUTO_DRY_PCT) dryFor += 1000; else dryFor = 0;
    if (dryFor >= 5000 && now >= autoNextAt && !scanStep) { if (pumpStart(AUTO_PUMP_SEC)) { autoNextAt = now + AUTO_WAIT_MS; dryFor = 0; } }
  }

  // ---- servo scan (left, centre, right) without blocking the loop
  if (scanStep && (int32_t)(now - scanNext) >= 0) {
    if (scanStep >= 1 && scanStep <= 3) {
      if (scanStep > 1) scanVal[scanStep - 2] = medianDistance();      // measure at the position reached before
      servoGo(scanStep == 1 ? SERVO_LEFT : scanStep == 2 ? SERVO_CENTRE : SERVO_RIGHT); scanNext = now + 550; scanStep++;
    } else if (scanStep == 4) {
      scanVal[2] = medianDistance(); servoGo(SERVO_CENTRE);
      Serial.print(F("SCAN,")); Serial.print(scanVal[0]); Serial.print(','); Serial.print(scanVal[1]); Serial.print(','); Serial.println(scanVal[2]);
      scanStep = 0;
    }
  }
  if (servo.attached() && (int32_t)(now - servoDetachAt) >= 0 && !scanStep) servo.detach();   // no buzzing, no wasted current

  // ---- telemetry
  if (now - tSoil >= 1000) {
    tSoil = now; soilPct = toPct(readRawSoil());
    Serial.print(F("SOIL,")); Serial.println(soilPct);
    Serial.print(F("DIST,")); Serial.println(distCm);
  }
  if (now - tEnv >= 2500 && moving == 'S') {                           // the DHT11 read takes a few ms: do it only while standing
    tEnv = now; dhtOk = readDHT11() || readDHT11();
    if (dhtOk) { Serial.print(F("ENV,")); Serial.print(tempC); Serial.print(','); Serial.println(humPct); } else Serial.println(F("ENV,ERR"));
  }
  if (edge != lastEdgeSent || now - tEdgeSend >= 2000) { lastEdgeSent = edge; tEdgeSend = now; Serial.print(F("EDGE,")); Serial.println(edge ? 1 : 0); }

  // ---- LCD, twice a second
  if (now - tLcd >= 500) {
    tLcd = now; char a[17], b[17];
    if (dhtOk) snprintf(a, sizeof(a), "S%d%% T%dC H%d%%", soilPct, tempC, humPct); else snprintf(a, sizeof(a), "Soil %d%%", soilPct);
    if (edge && safetyOn)           snprintf(b, sizeof(b), "TABLE EDGE!");
    else if (obstacle && safetyOn)  snprintf(b, sizeof(b), "OBSTACLE %dcm", distCm);
    else if (pumpOn)                snprintf(b, sizeof(b), "PUMP ON");
    else if (moving != 'S')         snprintf(b, sizeof(b), "MOVING %c", moving);
    else if (distCm > 0)            snprintf(b, sizeof(b), "READY D%dcm%s", distCm, autoWater ? " W" : "");
    else                            snprintf(b, sizeof(b), "READY");
    lcdShow(0, a); lcdShow(1, b);
  }
}
