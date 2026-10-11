/* Individual and all-motor tests for the confirmed DIRECT GPIO wiring.
 * Raise all wheels; upload with motor power off. Serial Monitor: 115200 baud.
 * Commands: LF+/-, RF+/-, LR+/-, RR+/-, ALL+, ALL-, LEFT, RIGHT, STOP.
 * Each test powers the selected motors for 1500 ms at 100% PWM, then stops.
 * This standalone sketch temporarily replaces the phone controller.
 */
#include <Arduino.h>
#include "test_commands.h"

struct MotorPins { const char* name; uint8_t pwm, in1, in2; };
// Positive means IN1/IN3 high, IN2/IN4 low; observe physical polarity.
const MotorPins motors[] = {
  {"LF", 26, 18, 19},  // #1 OUT3/4
  {"RF", 32, 21, 22},  // #2 OUT1/2
  {"LR", 25, 16, 17},  // #1 OUT1/2
  {"RR", 33, 4, 5},    // #2 OUT3/4
};
constexpr uint32_t TEST_MS = 1500, COAST_MS = 500;
constexpr uint8_t TEST_PWM = 255;  // 100% PWM; test with all wheels raised.
bool pwmReady = false, running = false, pending = false;
int directions[4] = {};
uint32_t stoppedAt = 0, startedAt = 0;
char line[12] = {};
unsigned length = 0;
bool overflow = false;

void stopMotors() {
  for (const auto& motor : motors) {
    if (pwmReady) ledcWrite(motor.pwm, 0);
    else digitalWrite(motor.pwm, LOW);
  }
  for (const auto& motor : motors) {
    digitalWrite(motor.in1, LOW);
    digitalWrite(motor.in2, LOW);
  }
  running = pending = false;
  stoppedAt = millis();
}

void command() {
  line[length] = 0;
  stopMotors();  // Every new command first disables all four channels.
  bool valid = !overflow && testDirections(line, directions);
  if (valid && strcmp(line, "STOP") == 0) {
    Serial.println("Stopped.");
  } else if (valid && pwmReady) {
    pending = true;
    Serial.printf("Queued %s; 500 ms coast, then 1500 ms at PWM %u/255.\n", line, TEST_PWM);
  } else Serial.println("Stopped. Use LF+/-, RF+/-, LR+/-, RR+/-, ALL+, ALL-, LEFT, RIGHT, STOP. PWM must be ready.");
  length = 0; overflow = false;
}

void setup() {
  for (const auto& motor : motors) {
    pinMode(motor.pwm, OUTPUT); digitalWrite(motor.pwm, LOW);
    pinMode(motor.in1, OUTPUT); digitalWrite(motor.in1, LOW);
    pinMode(motor.in2, OUTPUT); digitalWrite(motor.in2, LOW);
  }
  Serial.begin(115200);
  bool attached = true;
  for (const auto& motor : motors) attached = ledcAttach(motor.pwm, 10000, 8) && attached;
  if (!attached) {
    for (const auto& motor : motors) {
      ledcDetach(motor.pwm); pinMode(motor.pwm, OUTPUT); digitalWrite(motor.pwm, LOW);
    }
  }
  pwmReady = attached;
  stopMotors();
  Serial.println("KENNY direct-wiring motor test. All outputs stopped.");
  Serial.println("Raise wheels. Commands: LF+/-, RF+/-, LR+/-, RR+/-, ALL+, ALL-, LEFT, RIGHT, STOP.");
  if (!pwmReady) Serial.println("PWM initialization failed. Tests disabled.");
}

void loop() {
  // Bound serial work so incoming data cannot postpone automatic stopping.
  for (unsigned budget = 0; budget < 32 && Serial.available(); ++budget) {
    char c = Serial.read();
    if (c == '\r' || c == '\n') {
      if (length || overflow) command();
    } else if (length < sizeof(line) - 1) {
      line[length++] = c >= 'a' && c <= 'z' ? c - ('a' - 'A') : c;
    } else overflow = true;
  }
  uint32_t now = millis();
  if (pending && uint32_t(now - stoppedAt) >= COAST_MS) {
    for (unsigned i = 0; i < 4; ++i) {
      digitalWrite(motors[i].in1, directions[i] > 0 ? HIGH : LOW);
      digitalWrite(motors[i].in2, directions[i] < 0 ? HIGH : LOW);
    }
    bool written = true;
    for (unsigned i = 0; i < 4; ++i) {
      written = ledcWrite(motors[i].pwm, directions[i] ? TEST_PWM : 0) && written;
    }
    if (!written) {
      stopMotors(); Serial.println("PWM write failed. All motors stopped.");
    } else {
      pending = false; running = true; startedAt = now;
      for (unsigned i = 0; i < 4; ++i) {
        if (directions[i]) Serial.printf("Testing %s %c; EN GPIO%u, direction GPIO%u/%u.\n",
          motors[i].name, directions[i] > 0 ? '+' : '-', motors[i].pwm, motors[i].in1, motors[i].in2);
      }
    }
  }
  if (running && uint32_t(now - startedAt) >= TEST_MS) {
    stopMotors(); Serial.println("Test finished. All motors stopped.");
  }
  delay(1);
}
