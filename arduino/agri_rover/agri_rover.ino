// AgriSahayak rover - Arduino Uno R3 firmware
// Motor driver: L298N     Soil sensor: capacitive (analog)
// Serial speed: 9600
//
// Commands received (text, one per line):  F  B  L  R  S   and   V<0-255>  (speed)
//                                          C  = print the raw soil reading (for calibration)
// Data sent:  SOIL,<percent 0-100>  once every second
//
// SAFETY: if no command arrives for 700 ms while moving, the rover stops by itself.

// ---------- pins (L298N) ----------
const int ENA = 5;   // left side speed (PWM pin)
const int IN1 = 7;
const int IN2 = 8;
const int ENB = 6;   // right side speed (PWM pin)
const int IN3 = 9;
const int IN4 = 10;
const int SOIL_PIN = A0;

// ---------- soil calibration (change in Part 4 of the guide) ----------
int AIR_VALUE   = 520;   // raw reading with sensor in dry air   (0 %)
int WATER_VALUE = 260;   // raw reading with sensor in water     (100 %)

// ---------- settings ----------
const unsigned long CMD_TIMEOUT_MS = 700;
const unsigned long SOIL_EVERY_MS  = 1000;

int speedPwm = 150;
char moving = 'S';
unsigned long lastCmd = 0;
unsigned long lastSoil = 0;
String line = "";

void setSide(int in_a, int in_b, int en, int dir) {   // dir: 1 forward, -1 back, 0 stop
  if (dir > 0)      { digitalWrite(in_a, HIGH); digitalWrite(in_b, LOW);  analogWrite(en, speedPwm); }
  else if (dir < 0) { digitalWrite(in_a, LOW);  digitalWrite(in_b, HIGH); analogWrite(en, speedPwm); }
  else              { digitalWrite(in_a, LOW);  digitalWrite(in_b, LOW);  analogWrite(en, 0); }
}

void drive(char c) {
  moving = c;
  if (c == 'F')      { setSide(IN1, IN2, ENA,  1); setSide(IN3, IN4, ENB,  1); }
  else if (c == 'B') { setSide(IN1, IN2, ENA, -1); setSide(IN3, IN4, ENB, -1); }
  else if (c == 'L') { setSide(IN1, IN2, ENA, -1); setSide(IN3, IN4, ENB,  1); }  // spin left
  else if (c == 'R') { setSide(IN1, IN2, ENA,  1); setSide(IN3, IN4, ENB, -1); }  // spin right
  else               { setSide(IN1, IN2, ENA,  0); setSide(IN3, IN4, ENB,  0); moving = 'S'; }
}

int readRaw() {
  long sum = 0;
  for (int i = 0; i < 10; i++) { sum += analogRead(SOIL_PIN); delay(2); }
  return (int)(sum / 10);
}

int soilPercent() {
  int raw = readRaw();
  long pct = map(raw, AIR_VALUE, WATER_VALUE, 0, 100);   // capacitive sensor: lower raw = wetter
  if (pct < 0) pct = 0;
  if (pct > 100) pct = 100;
  return (int)pct;
}

void handleLine(String s) {
  s.trim();
  if (s.length() == 0) return;
  char c = toupper(s.charAt(0));
  if (c == 'V') {
    int v = s.substring(1).toInt();
    if (v < 0) v = 0;
    if (v > 255) v = 255;
    speedPwm = v;
    if (moving != 'S') drive(moving);   // apply new speed at once
  } else if (c == 'C') {
    Serial.print("RAW,");
    Serial.println(readRaw());
  } else if (c == 'F' || c == 'B' || c == 'L' || c == 'R' || c == 'S') {
    drive(c);
    lastCmd = millis();
  }
}

void setup() {
  pinMode(ENA, OUTPUT); pinMode(IN1, OUTPUT); pinMode(IN2, OUTPUT);
  pinMode(ENB, OUTPUT); pinMode(IN3, OUTPUT); pinMode(IN4, OUTPUT);
  drive('S');
  Serial.begin(9600);
  line.reserve(24);
  Serial.println("READY");
}

void loop() {
  while (Serial.available() > 0) {
    char ch = (char)Serial.read();
    if (ch == '\n' || ch == '\r') { handleLine(line); line = ""; }
    else if (line.length() < 20) { line += ch; }
  }
  if (moving != 'S' && millis() - lastCmd > CMD_TIMEOUT_MS) drive('S');   // safety stop
  if (millis() - lastSoil >= SOIL_EVERY_MS) {
    lastSoil = millis();
    Serial.print("SOIL,");
    Serial.println(soilPercent());
  }
}
