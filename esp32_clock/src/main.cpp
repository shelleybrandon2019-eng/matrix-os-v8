#include <Arduino.h>
#include <Arduino_GFX_Library.h>

// Waveshare ESP32-S3 LCD 1.47-inch board used by Matrix OS.
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
uint16_t C_RED;
uint16_t C_BLUE;

struct ClockState {
  int hour = 0;
  int minute = 0;
  int second = 0;
  String ampm = "--";
  String date = "";
  bool synced = false;
  uint32_t lastSync = 0;
} clockState;

enum class Effect : uint8_t {
  NONE,
  MELT,
  BULLET,
  AGENT,
  SCAN,
  GLITCH,
  BREACH,
};

Effect effect = Effect::NONE;
uint32_t effectStarted = 0;
uint32_t effectDuration = 0;
uint32_t nextEventAt = 0;
uint32_t lastFrame = 0;
String serialLine;

static constexpr int DIGIT_W = 50;
static constexpr int DIGIT_H = 122;
static constexpr int SEG_T = 11;
static constexpr int DIGIT_Y = 15;
static constexpr int DIGIT_X[4] = {8, 64, 143, 199};
static constexpr int COLON_X = 126;

const uint8_t DIGIT_MASKS[10] = {
  0b1111110, // 0
  0b0110000, // 1
  0b1101101, // 2
  0b1111001, // 3
  0b0110011, // 4
  0b1011011, // 5
  0b1011111, // 6
  0b1110000, // 7
  0b1111111, // 8
  0b1111011, // 9
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
  nextEventAt = millis() + static_cast<uint32_t>(random(20000, 60001));
}

uint16_t dimColor(uint8_t level) {
  switch (level) {
    case 0: return C_DIM;
    case 1: return C_MID;
    default: return C_GREEN;
  }
}

void drawPiece(int x, int y, int w, int h, uint16_t color,
               uint32_t seed, float melt, int tearAmp) {
  if (melt > 0.001f) {
    const int drop = hashRange(seed, 45, 155);
    const int drift = hashRange(seed ^ 0xA53u, -24, 24);
    y += static_cast<int>(drop * melt);
    x += static_cast<int>(drift * melt);
    if (melt > 0.82f && (hash32(seed ^ millis() / 45) & 3u) == 0u) return;
  }
  if (tearAmp != 0) {
    const int band = max(0, y / 13);
    const int direction = ((band + static_cast<int>(millis() / 55)) & 1) ? 1 : -1;
    x += direction * tearAmp * (1 + (band % 3));
  }
  if (x + w < 0 || x >= SCREEN_W || y + h < 0 || y >= SCREEN_H) return;
  gfx->fillRect(x, y, w, h, color);
}

void drawSegmentPieces(int x, int y, int w, int h, bool horizontal,
                       uint16_t color, uint32_t seed,
                       float melt = 0.0f, int tearAmp = 0) {
  const int pieces = 6;
  if (horizontal) {
    const int pieceW = max(2, w / pieces);
    for (int i = 0; i < pieces; ++i) {
      const int px = x + i * pieceW;
      const int pw = (i == pieces - 1) ? (x + w - px) : pieceW - 1;
      drawPiece(px, y, pw, h, color, seed + i * 97u, melt, tearAmp);
    }
  } else {
    const int pieceH = max(2, h / pieces);
    for (int i = 0; i < pieces; ++i) {
      const int py = y + i * pieceH;
      const int ph = (i == pieces - 1) ? (y + h - py) : pieceH - 1;
      drawPiece(x, py, w, ph, color, seed + i * 131u, melt, tearAmp);
    }
  }
}

void drawDigit(int digit, int x, int y, uint16_t color,
               uint32_t seed, float melt = 0.0f, int tearAmp = 0) {
  if (digit < 0 || digit > 9) return;
  const uint8_t mask = DIGIT_MASKS[digit];
  const int halfH = DIGIT_H / 2;
  const int horizontalW = DIGIT_W - SEG_T * 2;
  const int verticalH = halfH - SEG_T * 2;

  // Segment order: A B C D E F G = bits 6..0.
  if (mask & 0b1000000) drawSegmentPieces(x + SEG_T, y, horizontalW, SEG_T, true, color, seed + 1, melt, tearAmp);
  if (mask & 0b0100000) drawSegmentPieces(x + DIGIT_W - SEG_T, y + SEG_T, SEG_T, verticalH, false, color, seed + 2, melt, tearAmp);
  if (mask & 0b0010000) drawSegmentPieces(x + DIGIT_W - SEG_T, y + halfH + SEG_T / 2, SEG_T, verticalH, false, color, seed + 3, melt, tearAmp);
  if (mask & 0b0001000) drawSegmentPieces(x + SEG_T, y + DIGIT_H - SEG_T, horizontalW, SEG_T, true, color, seed + 4, melt, tearAmp);
  if (mask & 0b0000100) drawSegmentPieces(x, y + halfH + SEG_T / 2, SEG_T, verticalH, false, color, seed + 5, melt, tearAmp);
  if (mask & 0b0000010) drawSegmentPieces(x, y + SEG_T, SEG_T, verticalH, false, color, seed + 6, melt, tearAmp);
  if (mask & 0b0000001) drawSegmentPieces(x + SEG_T, y + halfH - SEG_T / 2, horizontalW, SEG_T, true, color, seed + 7, melt, tearAmp);
}

void drawColon(uint16_t color, float melt = 0.0f, int tearAmp = 0) {
  drawPiece(COLON_X, DIGIT_Y + 37, 10, 10, color, 7001, melt, tearAmp);
  drawPiece(COLON_X, DIGIT_Y + 78, 10, 10, color, 7002, melt, tearAmp);
}

void drawLabels(uint16_t color, bool showSeconds = true) {
  gfx->setTextColor(color);
  gfx->setTextSize(2);
  gfx->setCursor(270, 112);
  gfx->print(clockState.ampm);
  if (showSeconds) {
    char seconds[4];
    snprintf(seconds, sizeof(seconds), "%02d", clockState.second);
    gfx->setCursor(273, 82);
    gfx->print(seconds);
  }
}

void drawClockCore(uint16_t color, float melt = 0.0f, int tearAmp = 0,
                   int xOffset = 0, bool labels = true) {
  const int h = clockState.synced ? clockState.hour : 0;
  const int m = clockState.synced ? clockState.minute : 0;
  int digits[4] = {h / 10, h % 10, m / 10, m % 10};
  if (!clockState.synced) digits[0] = digits[1] = digits[2] = digits[3] = 8;

  for (int i = 0; i < 4; ++i) {
    drawDigit(digits[i], DIGIT_X[i] + xOffset, DIGIT_Y, color,
              1000u + i * 100u, melt, tearAmp);
  }
  drawColon(color, melt, tearAmp);
  if (labels) drawLabels(color);
}

void drawNormalClock() {
  drawClockCore(C_GREEN);
  if (!clockState.synced) {
    gfx->setTextColor(C_RED);
    gfx->setTextSize(2);
    gfx->setCursor(268, 142);
    gfx->print("LINK");
  }
}

void drawMelt(float p) {
  const float melt = (p < 0.52f) ? (p / 0.52f) : ((1.0f - p) / 0.48f);
  drawClockCore(melt > 0.70f ? C_MID : C_GREEN, constrain(melt, 0.0f, 1.0f));
  if (p > 0.45f && p < 0.70f) {
    gfx->setTextColor(C_DIM);
    gfx->setTextSize(1);
    gfx->setCursor(130, 160);
    gfx->print("REFORMING");
  }
}

void drawBullet(float p) {
  const float wave = sinf(p * PI);
  drawClockCore(C_DIM, 0.0f, 0, -18, false);
  drawClockCore(C_MID, 0.0f, 0, -9, false);
  drawClockCore(C_GREEN, 0.0f, 0, static_cast<int>(wave * 7), true);
  const int scanX = static_cast<int>(p * SCREEN_W);
  gfx->drawFastVLine(scanX, 0, SCREEN_H, C_HEAD);
  gfx->setTextColor(C_HEAD);
  gfx->setTextSize(1);
  gfx->setCursor(4, 158);
  gfx->print("BULLET TIME");
}

void drawAgentFigure(int x, int y, bool scanning) {
  gfx->fillCircle(x, y, 11, C_BLACK);
  gfx->drawCircle(x, y, 11, C_GREEN);
  gfx->fillRect(x - 10, y + 10, 20, 34, C_BLACK);
  gfx->drawRect(x - 10, y + 10, 20, 34, C_GREEN);
  gfx->drawLine(x - 8, y + 44, x - 16, y + 64, C_GREEN);
  gfx->drawLine(x + 8, y + 44, x + 16, y + 64, C_GREEN);
  gfx->drawLine(x - 10, y + 18, x - 24, y + 34, C_GREEN);
  gfx->drawLine(x + 10, y + 18, x + 24, y + 34, C_GREEN);
  gfx->drawFastHLine(x - 8, y - 2, 6, C_HEAD);
  gfx->drawFastHLine(x + 2, y - 2, 6, C_HEAD);
  if (scanning) {
    for (int i = 0; i < 4; ++i) {
      gfx->drawLine(x + 11, y, x + 55, y - 24 + i * 16, dimColor(i > 1 ? 1 : 0));
    }
  }
}

void drawAgent(float p, bool scanOnly) {
  drawClockCore(C_DIM);
  int x;
  if (scanOnly) {
    x = 240;
  } else {
    x = static_cast<int>(-35 + p * (SCREEN_W + 70));
  }
  const bool scanning = scanOnly || p > 0.58f;
  drawAgentFigure(x, 61, scanning);
  gfx->setTextColor(C_MID);
  gfx->setTextSize(1);
  gfx->setCursor(5, 160);
  gfx->print(scanning ? "AGENT SCAN" : "AGENT MOVEMENT");
}

void drawGlitch(float p) {
  const float envelope = sinf(p * PI);
  const int amp = max(1, static_cast<int>(envelope * 7));
  drawClockCore(C_GREEN, 0.0f, amp);
  if ((millis() / 70) & 1u) {
    const int y = random(10, 160);
    gfx->drawFastHLine(0, y, SCREEN_W, C_HEAD);
  }
}

void drawBreach(float p) {
  const float envelope = sinf(p * PI);
  const int amp = static_cast<int>(envelope * 9);
  drawClockCore(p < 0.72f ? C_RED : C_GREEN, 0.0f, amp);
  for (int i = 0; i < 5; ++i) {
    const int y = 18 + i * 31 + ((millis() / 50 + i * 9) % 13);
    gfx->drawFastHLine(0, y, SCREEN_W, (i & 1) ? C_RED : C_MID);
  }
  gfx->setTextColor(C_RED);
  gfx->setTextSize(2);
  gfx->setCursor(76, 148);
  gfx->print("SIGNAL BREACH");
}

void startEffect(Effect next) {
  effect = next;
  effectStarted = millis();
  switch (effect) {
    case Effect::MELT:   effectDuration = 2200; break;
    case Effect::BULLET: effectDuration = 1850; break;
    case Effect::AGENT:  effectDuration = 2200; break;
    case Effect::SCAN:   effectDuration = 1900; break;
    case Effect::GLITCH: effectDuration = 1450; break;
    case Effect::BREACH: effectDuration = 2050; break;
    default: effectDuration = 0; break;
  }
}

Effect parseEffect(String name) {
  name.trim();
  name.toUpperCase();
  if (name == "MELT") return Effect::MELT;
  if (name == "BULLET") return Effect::BULLET;
  if (name == "AGENT") return Effect::AGENT;
  if (name == "SCAN") return Effect::SCAN;
  if (name == "GLITCH") return Effect::GLITCH;
  if (name == "BREACH") return Effect::BREACH;
  return Effect::NONE;
}

void parseTime(String line) {
  // TIME|HH|MM|SS|AM|YYYY-MM-DD
  int fields[5];
  int found = 0;
  for (int i = 0; i < static_cast<int>(line.length()) && found < 5; ++i) {
    if (line[i] == '|') fields[found++] = i;
  }
  if (found < 5) return;
  clockState.hour = line.substring(fields[0] + 1, fields[1]).toInt();
  clockState.minute = line.substring(fields[1] + 1, fields[2]).toInt();
  clockState.second = line.substring(fields[2] + 1, fields[3]).toInt();
  clockState.ampm = line.substring(fields[3] + 1, fields[4]);
  clockState.date = line.substring(fields[4] + 1);
  clockState.synced = true;
  clockState.lastSync = millis();
}

void handleCommand(String line) {
  line.trim();
  if (line.startsWith("TIME|")) {
    parseTime(line);
  } else if (line.startsWith("EVENT|")) {
    const Effect requested = parseEffect(line.substring(6));
    if (requested != Effect::NONE) startEffect(requested);
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
      static_cast<float>(millis() - effectStarted) / (effectDuration ? effectDuration : 1u),
      0.0f, 1.0f);
  switch (effect) {
    case Effect::MELT: drawMelt(p); break;
    case Effect::BULLET: drawBullet(p); break;
    case Effect::AGENT: drawAgent(p, false); break;
    case Effect::SCAN: drawAgent(p, true); break;
    case Effect::GLITCH: drawGlitch(p); break;
    case Effect::BREACH: drawBreach(p); break;
    default: drawNormalClock(); break;
  }
}

void setup() {
  pinMode(LCD_BL, OUTPUT);
  digitalWrite(LCD_BL, HIGH);
  Serial.begin(115200);
  serialLine.reserve(192);
  randomSeed(esp_random());

  gfx->begin(40000000);
  gfx->setRotation(1); // 320x172 landscape, clockwise.
  gfx->setTextWrap(false);

  C_BLACK = gfx->color565(0, 0, 0);
  C_DIM   = gfx->color565(0, 42, 14);
  C_MID   = gfx->color565(0, 125, 38);
  C_GREEN = gfx->color565(0, 255, 70);
  C_HEAD  = gfx->color565(205, 255, 218);
  C_RED   = gfx->color565(255, 42, 32);
  C_BLUE  = gfx->color565(35, 125, 255);

  gfx->fillScreen(C_BLACK);
  scheduleNextEvent();
  Serial.println("READY|ESP32_HUB_CLOCK_V10");
}

void loop() {
  pollSerial();

  if (effect != Effect::NONE && millis() - effectStarted >= effectDuration) {
    effect = Effect::NONE;
    scheduleNextEvent();
  }

  if (effect == Effect::NONE && clockState.synced && millis() >= nextEventAt) {
    const int choice = random(0, 6);
    startEffect(static_cast<Effect>(choice + 1));
  }

  // Mark the link stale after 90 seconds, but keep the last known time visible.
  if (clockState.synced && millis() - clockState.lastSync > 90000) {
    clockState.ampm = "LK";
  }

  if (millis() - lastFrame >= 33) {
    lastFrame = millis();
    render();
  }
  delay(1);
}
