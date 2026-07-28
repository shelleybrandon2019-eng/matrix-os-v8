#include <Arduino.h>
#include <Arduino_GFX_Library.h>

static constexpr int LCD_MOSI = 45;
static constexpr int LCD_SCLK = 40;
static constexpr int LCD_CS   = 42;
static constexpr int LCD_DC   = 41;
static constexpr int LCD_RST  = 39;
static constexpr int LCD_BL   = 48;

static constexpr int PANEL_W = 172;
static constexpr int PANEL_H = 320;
static constexpr int SCREEN_W = 320;
static constexpr int SCREEN_H = 172;

Arduino_DataBus *bus = new Arduino_ESP32SPI(
    LCD_DC, LCD_CS, LCD_SCLK, LCD_MOSI, GFX_NOT_DEFINED);
Arduino_GFX *gfx = new Arduino_ST7789(
    bus, LCD_RST, 0, true, PANEL_W, PANEL_H, 34, 0, 34, 0);

uint16_t C_BLACK;
uint16_t C_DIM;
uint16_t C_MID;
uint16_t C_GREEN;
uint16_t C_HEAD;

struct ClockState {
  int hour = 12;
  int minute = 0;
  int second = 0;
  String ampm = "--";
  bool synced = false;
  uint32_t lastSyncMs = 0;
} clockState;

enum class Effect : uint8_t { NONE, MELT, PHONE };
Effect effect = Effect::NONE;
uint32_t effectStartedMs = 0;
uint32_t effectDurationMs = 0;
uint32_t nextEventMs = 0;
uint32_t lastFrameMs = 0;
String serialLine;

static constexpr int DIGIT_W = 50;
static constexpr int DIGIT_H = 122;
static constexpr int SEG_T = 11;
static constexpr int DIGIT_Y = 15;
static constexpr int DIGIT_X[4] = {8, 64, 143, 199};
static constexpr int COLON_X = 126;

const uint8_t DIGIT_MASKS[10] = {
  0b1111110, 0b0110000, 0b1101101, 0b1111001, 0b0110011,
  0b1011011, 0b1011111, 0b1110000, 0b1111111, 0b1111011,
};

uint32_t hash32(uint32_t value) {
  value ^= value >> 16;
  value *= 0x7feb352d;
  value ^= value >> 15;
  value *= 0x846ca68b;
  value ^= value >> 16;
  return value;
}

int hashRange(uint32_t seed, int low, int high) {
  if (high <= low) return low;
  return low + static_cast<int>(hash32(seed) % static_cast<uint32_t>(high - low + 1));
}

void scheduleNextEvent() {
  nextEventMs = millis() + static_cast<uint32_t>(random(30000, 90001));
}

void drawPiece(int x, int y, int w, int h, uint16_t color,
               uint32_t seed, float melt = 0.0f) {
  if (melt > 0.001f) {
    const int drop = hashRange(seed, 35, 150);
    const int drift = hashRange(seed ^ 0xA53u, -22, 22);
    y += static_cast<int>(drop * melt);
    x += static_cast<int>(drift * melt);
    if (melt > 0.80f && (hash32(seed ^ millis() / 45) & 3u) == 0u) return;
  }
  if (x + w < 0 || x >= SCREEN_W || y + h < 0 || y >= SCREEN_H) return;
  gfx->fillRect(x, y, w, h, color);
}

void drawSegmentPieces(int x, int y, int w, int h, bool horizontal,
                       uint16_t color, uint32_t seed, float melt = 0.0f) {
  const int pieces = 6;
  if (horizontal) {
    const int pieceW = max(2, w / pieces);
    for (int i = 0; i < pieces; ++i) {
      const int px = x + i * pieceW;
      const int pw = (i == pieces - 1) ? (x + w - px) : pieceW - 1;
      drawPiece(px, y, pw, h, color, seed + i * 97u, melt);
    }
  } else {
    const int pieceH = max(2, h / pieces);
    for (int i = 0; i < pieces; ++i) {
      const int py = y + i * pieceH;
      const int ph = (i == pieces - 1) ? (y + h - py) : pieceH - 1;
      drawPiece(x, py, w, ph, color, seed + i * 131u, melt);
    }
  }
}

void drawDigit(int digit, int x, int y, uint16_t color,
               uint32_t seed, float melt = 0.0f) {
  if (digit < 0 || digit > 9) return;
  const uint8_t mask = DIGIT_MASKS[digit];
  const int halfH = DIGIT_H / 2;
  const int horizontalW = DIGIT_W - SEG_T * 2;
  const int verticalH = halfH - SEG_T * 2;

  if (mask & 0b1000000) drawSegmentPieces(x + SEG_T, y, horizontalW, SEG_T, true, color, seed + 1, melt);
  if (mask & 0b0100000) drawSegmentPieces(x + DIGIT_W - SEG_T, y + SEG_T, SEG_T, verticalH, false, color, seed + 2, melt);
  if (mask & 0b0010000) drawSegmentPieces(x + DIGIT_W - SEG_T, y + halfH + SEG_T / 2, SEG_T, verticalH, false, color, seed + 3, melt);
  if (mask & 0b0001000) drawSegmentPieces(x + SEG_T, y + DIGIT_H - SEG_T, horizontalW, SEG_T, true, color, seed + 4, melt);
  if (mask & 0b0000100) drawSegmentPieces(x, y + halfH + SEG_T / 2, SEG_T, verticalH, false, color, seed + 5, melt);
  if (mask & 0b0000010) drawSegmentPieces(x, y + SEG_T, SEG_T, verticalH, false, color, seed + 6, melt);
  if (mask & 0b0000001) drawSegmentPieces(x + SEG_T, y + halfH - SEG_T / 2, horizontalW, SEG_T, true, color, seed + 7, melt);
}

void drawClockCore(uint16_t color, float melt = 0.0f) {
  const int h = clockState.synced ? clockState.hour : 0;
  const int m = clockState.synced ? clockState.minute : 0;
  int digits[4] = {h / 10, h % 10, m / 10, m % 10};
  if (!clockState.synced) digits[0] = digits[1] = digits[2] = digits[3] = 8;

  for (int i = 0; i < 4; ++i) {
    if (i == 0 && digits[i] == 0) continue;
    drawDigit(digits[i], DIGIT_X[i], DIGIT_Y, color, 1000u + i * 100u, melt);
  }

  drawPiece(COLON_X, DIGIT_Y + 37, 10, 10, color, 7001, melt);
  drawPiece(COLON_X, DIGIT_Y + 78, 10, 10, color, 7002, melt);

  gfx->setTextColor(color);
  gfx->setTextSize(2);
  gfx->setCursor(270, 112);
  gfx->print(clockState.ampm);

  char seconds[4];
  snprintf(seconds, sizeof(seconds), "%02d", clockState.second);
  gfx->setCursor(273, 82);
  gfx->print(seconds);
}

void drawNormalClock() {
  drawClockCore(C_GREEN);
  if (!clockState.synced) {
    gfx->setTextColor(C_DIM);
    gfx->setTextSize(1);
    gfx->setCursor(270, 147);
    gfx->print("WAIT");
  }
}

void drawMelt(float p) {
  float melt;
  if (p < 0.48f) melt = p / 0.48f;
  else melt = (1.0f - p) / 0.52f;
  melt = constrain(melt, 0.0f, 1.0f);
  drawClockCore(melt > 0.70f ? C_MID : C_GREEN, melt);
  if (p > 0.42f && p < 0.68f) {
    gfx->setTextColor(C_DIM);
    gfx->setTextSize(1);
    gfx->setCursor(126, 160);
    gfx->print("REFORMING");
  }
}

void drawPhoneIcon(int cx, int cy, float glow) {
  const uint16_t color = glow > 0.6f ? C_HEAD : C_GREEN;
  gfx->drawCircle(cx, cy, 29, color);
  gfx->drawCircle(cx, cy, 28, C_MID);
  gfx->drawArc(cx, cy, 24, 18, 215, 325, color);
  gfx->fillCircle(cx - 18, cy + 13, 5, color);
  gfx->fillCircle(cx + 18, cy + 13, 5, color);
  gfx->drawLine(cx - 17, cy + 9, cx - 8, cy - 3, color);
  gfx->drawLine(cx + 17, cy + 9, cx + 8, cy - 3, color);
}

void drawPhoneTrace(float p) {
  const float pulse = 0.5f + 0.5f * sinf(p * PI * 8.0f);
  const int cx = 72;
  const int cy = 76;
  drawPhoneIcon(cx, cy, pulse);

  for (int ring = 0; ring < 4; ++ring) {
    const int radius = 38 + ring * 10 + static_cast<int>(p * 8.0f);
    const uint16_t color = ring < 2 ? C_MID : C_DIM;
    gfx->drawCircle(cx, cy, radius, color);
  }

  const int traceStart = 115;
  const int traceEnd = 305;
  const int traceX = traceStart + static_cast<int>((traceEnd - traceStart) * p);
  gfx->drawFastHLine(traceStart, 77, max(1, traceX - traceStart), C_GREEN);
  gfx->drawFastVLine(traceX, 20, 115, C_HEAD);

  for (int i = 0; i < 12; ++i) {
    const int x = traceStart + i * 16;
    const int h = hashRange(i * 73u + millis() / 80u, 6, 42);
    gfx->drawFastVLine(x, 77 - h / 2, h, (i % 3 == 0) ? C_GREEN : C_DIM);
  }

  gfx->setTextColor(C_HEAD);
  gfx->setTextSize(2);
  gfx->setCursor(128, 25);
  gfx->print("CALL TRACE");

  gfx->setTextColor(C_GREEN);
  gfx->setTextSize(1);
  gfx->setCursor(128, 112);
  gfx->print(p < 0.45f ? "DIALING..." : (p < 0.82f ? "LOCATING SIGNAL" : "CONNECTED"));

  char number[18];
  snprintf(number, sizeof(number), "555-%03d-%04d",
           hashRange(991u, 100, 999), hashRange(1771u, 0, 9999));
  gfx->setTextColor(C_MID);
  gfx->setCursor(128, 132);
  gfx->print(number);
}

void startEffect(Effect next) {
  effect = next;
  effectStartedMs = millis();
  effectDurationMs = (effect == Effect::MELT) ? 2300 : 2800;
}

void parseTime(const String &line) {
  int bars[5];
  int found = 0;
  for (int i = 0; i < static_cast<int>(line.length()) && found < 5; ++i) {
    if (line[i] == '|') bars[found++] = i;
  }
  if (found < 5) return;
  clockState.hour = line.substring(bars[0] + 1, bars[1]).toInt();
  clockState.minute = line.substring(bars[1] + 1, bars[2]).toInt();
  clockState.second = line.substring(bars[2] + 1, bars[3]).toInt();
  clockState.ampm = line.substring(bars[3] + 1, bars[4]);
  clockState.synced = true;
  clockState.lastSyncMs = millis();
}

void handleCommand(String line) {
  line.trim();
  if (line.startsWith("TIME|")) {
    parseTime(line);
  } else if (line == "EVENT|MELT") {
    startEffect(Effect::MELT);
  } else if (line == "EVENT|PHONE") {
    startEffect(Effect::PHONE);
  } else if (line.startsWith("HELLO|")) {
    Serial.println("READY|ESP32_HUB_CLOCK_V10");
  } else if (line == "PING") {
    Serial.println("PONG|ESP32_HUB_CLOCK_V10");
  }
}

void pollSerial() {
  while (Serial.available()) {
    const char ch = static_cast<char>(Serial.read());
    if (ch == '\n') {
      handleCommand(serialLine);
      serialLine = "";
    } else if (ch != '\r' && serialLine.length() < 180) {
      serialLine += ch;
    }
  }
}

void render() {
  gfx->fillScreen(C_BLACK);
  if (effect == Effect::NONE) {
    drawNormalClock();
    return;
  }
  const float p = constrain(
      static_cast<float>(millis() - effectStartedMs) /
          static_cast<float>(effectDurationMs ? effectDurationMs : 1u),
      0.0f, 1.0f);
  if (effect == Effect::MELT) drawMelt(p);
  else drawPhoneTrace(p);
}

void setup() {
  pinMode(LCD_BL, OUTPUT);
  digitalWrite(LCD_BL, HIGH);
  Serial.begin(115200);
  serialLine.reserve(192);
  randomSeed(esp_random());

  gfx->begin(40000000);
  gfx->setRotation(1);
  gfx->setTextWrap(false);

  C_BLACK = gfx->color565(0, 0, 0);
  C_DIM   = gfx->color565(0, 42, 14);
  C_MID   = gfx->color565(0, 125, 38);
  C_GREEN = gfx->color565(0, 255, 70);
  C_HEAD  = gfx->color565(205, 255, 218);

  gfx->fillScreen(C_BLACK);
  scheduleNextEvent();
  Serial.println("READY|ESP32_HUB_CLOCK_V10");
}

void loop() {
  pollSerial();

  if (effect != Effect::NONE && millis() - effectStartedMs >= effectDurationMs) {
    effect = Effect::NONE;
    scheduleNextEvent();
  }

  if (effect == Effect::NONE && clockState.synced && millis() >= nextEventMs) {
    startEffect(random(0, 100) < 62 ? Effect::MELT : Effect::PHONE);
  }

  if (millis() - lastFrameMs >= 33) {
    lastFrameMs = millis();
    render();
  }
  delay(1);
}
