#include <Arduino.h>
#include <ArduinoJson.h>

// Matrix OS V8 sidecar firmware.
// The Raspberry Pi is the controller. It sends one JSON object per line over USB serial.
// Screen rendering will be added after the exact display board/controller is identified.

static String inputLine;

void showEvent(const char* kind,
               const char* title,
               const char* value,
               const char* accent,
               unsigned long durationMs) {
  // Temporary serial proof. This function becomes the real screen renderer next.
  Serial.printf("EVENT kind=%s title=%s value=%s accent=%s duration=%lu\n",
                kind, title, value, accent, durationMs);
}

void handleLine(const String& line) {
  JsonDocument doc;
  DeserializationError error = deserializeJson(doc, line);

  if (error) {
    Serial.printf("ERR bad_json %s\n", error.c_str());
    return;
  }

  const char* kind = doc["kind"] | "status";
  const char* title = doc["title"] | "MATRIX OS V8";
  const char* value = doc["value"] | "ONLINE";
  const char* accent = doc["accent"] | "green";
  unsigned long durationMs = doc["duration_ms"] | 8000UL;

  showEvent(kind, title, value, accent, durationMs);
  Serial.println("ACK");
}

void setup() {
  Serial.begin(115200);
  unsigned long started = millis();
  while (!Serial && millis() - started < 3000) {
    delay(10);
  }

  inputLine.reserve(512);
  Serial.println();
  Serial.println("MATRIX_OS_V8_SIDECAR_READY");
  Serial.println("ROLE=DISPLAY_ONLY CONTROLLER=RASPBERRY_PI");
}

void loop() {
  while (Serial.available() > 0) {
    char c = static_cast<char>(Serial.read());

    if (c == '\n') {
      inputLine.trim();
      if (!inputLine.isEmpty()) {
        handleLine(inputLine);
      }
      inputLine = "";
    } else if (c != '\r') {
      if (inputLine.length() < 500) {
        inputLine += c;
      } else {
        inputLine = "";
        Serial.println("ERR line_too_long");
      }
    }
  }
}
