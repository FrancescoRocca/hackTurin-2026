// LARP CROSSWALK - LED ring, passive buzzer and Grove LCD effects.
// Extracted from Sentinel; no vision, sensors, counters or dashboard required.
#include "Arduino_RouterBridge.h"
#include <Wire.h>
#include <string.h>
#include <zephyr/kernel.h>

#define PIN_BUZZER 5
#define BUZZER_DUTY_PCT 1
#define BUZZER_PWM_BITS 10
#define BUZZER_BEEP_ON_MS 200
#define BUZZER_BEEP_OFF_MS 300

static int buzzer_duty_value() {
  return ((1 << BUZZER_PWM_BITS) - 1) * BUZZER_DUTY_PCT / 100;
}

// ---------------------------------------------------------------------------
// Grove 16x2 LCD (RGB backlight, JHD1313M1/AiP31068 controller)
// ---------------------------------------------------------------------------
// The module exposes two I2C addresses: 0x3E for the display (HD44780) and
// 0x62 for the RGB backlight (PCA9633 driver). It connects to the Qwiic
// connector (Wire1 bus) or to the SDA/SCL D20/D21 pins (Wire bus): the code
// detects it automatically on whichever bus answers, so the wiring can change.

#define GROVE_LCD_ADDR 0x3E
#define GROVE_RGB_ADDR 0x62
#define LCD_COLS 16
#define LCD_ROWS 2

static TwoWire *lcd_bus = nullptr;
static uint32_t lcd_error_count = 0;
static int g_lcd_bus_id = 0;  // 0 = absent, 1 = D20/D21 header, 2 = Qwiic

static bool i2c_present(TwoWire &bus, uint8_t addr) {
  bus.beginTransmission(addr);
  return bus.endTransmission() == 0;
}

static void lcd_write(uint8_t control, uint8_t value) {
  if (lcd_bus == nullptr) return;
  lcd_bus->beginTransmission(GROVE_LCD_ADDR);
  lcd_bus->write(control);
  lcd_bus->write(value);
  if (lcd_bus->endTransmission() != 0) lcd_error_count++;
}

static void lcd_command(uint8_t cmd) { lcd_write(0x80, cmd); }

static void lcd_set_rgb(uint8_t r, uint8_t g, uint8_t b) {
  if (lcd_bus == nullptr) return;
  auto set_reg = [](uint8_t reg, uint8_t value) {
    lcd_bus->beginTransmission(GROVE_RGB_ADDR);
    lcd_bus->write(reg);
    lcd_bus->write(value);
    lcd_bus->endTransmission();
  };
  set_reg(0x00, 0x00);  // MODE1: normal operation
  set_reg(0x01, 0x00);  // MODE2
  set_reg(0x08, 0xAA);  // LEDOUT: all channels driven by PWM
  set_reg(0x04, r);     // PWM red
  set_reg(0x03, g);     // PWM green
  set_reg(0x02, b);     // PWM blue
}

static void lcd_set_cursor(uint8_t col, uint8_t row) {
  static const uint8_t row_offsets[LCD_ROWS] = {0x00, 0x40};
  lcd_command(0x80 | (col + row_offsets[row & 0x01]));
}

static void lcd_print_line(uint8_t row, const String &text) {
  lcd_set_cursor(0, row);
  uint8_t i;
  for (i = 0; i < text.length() && i < LCD_COLS; i++) {
    lcd_write(0x40, (uint8_t)text[i]);
  }
  // Pad the row with spaces to erase the previous text.
  for (; i < LCD_COLS; i++) {
    lcd_write(0x40, ' ');
  }
}

static bool lcd_begin() {
  TwoWire *candidates[] = {&Wire1, &Wire};  // Qwiic first, then the UNO header
  const int ids[] = {2, 1};                 // id associated with each bus
  for (size_t i = 0; i < 2; i++) {
    candidates[i]->begin();
    if (i2c_present(*candidates[i], GROVE_LCD_ADDR)) {
      lcd_bus = candidates[i];
      g_lcd_bus_id = ids[i];
      break;
    }
  }
  if (lcd_bus == nullptr) return false;

  delay(50);
  lcd_command(0x28);  // function set: 2 rows, 5x8 font
  delayMicroseconds(4500);
  lcd_command(0x28);
  delayMicroseconds(150);
  lcd_command(0x28);
  lcd_command(0x0C);  // display on, cursor off, blink off
  lcd_command(0x01);  // clear
  delay(2);
  lcd_command(0x06);  // entry mode: cursor moves right, no shift
  lcd_command(0x02);  // home
  delay(2);

  lcd_set_rgb(0, 180, 90);  // SENTINELLA green backlight
  return true;
}

// ---------------------------------------------------------------------------
// Grove RGB LED Ring (16 x WS2813 Mini) sul pin D6
// ---------------------------------------------------------------------------
// The WS2813 is a single-wire addressable LED (@800 kHz protocol). The
// sketch has no access to fast SPI/PWM, so the data stream is generated in
// software with digitalWrite() and delays calibrated at startup (measured in
// the field: digitalWrite ~0.25 us -> timing within spec). Frames are in GRB order.

#define RING_PIN 6
#define RING_LEDS 16
#define RING_RESET_US 320

static uint8_t ring_frame[RING_LEDS * 3];
static uint32_t ring_frame_count = 0;
static float ring_call_us = 0.25f;
static float ring_iter_ns = 30.0f;
static uint32_t ring_hi0, ring_hi1, ring_lo0, ring_lo1;

static inline void ring_nops(uint32_t n) {
  for (volatile uint32_t i = 0; i < n; i++) {
    __asm__ __volatile__("nop");
  }
}

static inline uint32_t ring_us_to_iters(float us) {
  if (us <= 0.0f) return 0;
  return (uint32_t)((us * 1000.0f) / ring_iter_ns + 0.5f);
}

static float ring_measure_call_us() {
  const int N = 50000;
  digitalWrite(RING_PIN, LOW);
  unsigned long t0 = micros();
  for (int i = 0; i < N; i++) {
    digitalWrite(RING_PIN, HIGH);
    digitalWrite(RING_PIN, LOW);
  }
  unsigned long t1 = micros();
  return (float)(t1 - t0) / (2.0f * (float)N);  // us per call
}

static float ring_measure_iter_ns() {
  const uint32_t N = 20000;
  unsigned long t0 = micros();
  ring_nops(N);
  unsigned long t1 = micros();
  return (float)(t1 - t0) * 1000.0f / (float)N;  // ns per iteration
}

static void ring_send() {
  // Keep threads from switching mid-frame, but let UART interrupts run
  // between pixels. Masking IRQs for all 16 pixels loses Bridge UART bytes.
  k_sched_lock();
  for (int pixel = 0; pixel < RING_LEDS; pixel++) {
    unsigned int key = irq_lock();
    for (int channel = 0; channel < 3; channel++) {
      uint8_t b = ring_frame[pixel * 3 + channel];
      for (int bit = 7; bit >= 0; bit--) {
        bool one = (b >> bit) & 1;
        digitalWrite(RING_PIN, HIGH);
        ring_nops(one ? ring_hi1 : ring_hi0);
        digitalWrite(RING_PIN, LOW);
        ring_nops(one ? ring_lo1 : ring_lo0);
      }
    }
    irq_unlock(key);
  }
  k_sched_unlock();
  delayMicroseconds(RING_RESET_US);
  ring_frame_count++;
}

static void ring_begin() {
  pinMode(RING_PIN, OUTPUT);
  ring_call_us = ring_measure_call_us();
  ring_iter_ns = ring_measure_iter_ns();
  // WS2813 target timings (us): high 0.35/0.70, low 0.90/0.55.
  ring_hi0 = ring_us_to_iters(0.35f - ring_call_us);
  ring_hi1 = ring_us_to_iters(0.70f - ring_call_us);
  ring_lo0 = ring_us_to_iters(0.90f - ring_call_us);
  ring_lo1 = ring_us_to_iters(0.55f - ring_call_us);
}

static void ring_set(size_t i, uint8_t r, uint8_t g, uint8_t b) {
  ring_frame[i * 3 + 0] = g;  // WS2813 = GRB
  ring_frame[i * 3 + 1] = r;
  ring_frame[i * 3 + 2] = b;
}

static void ring_fill(uint8_t r, uint8_t g, uint8_t b) {
  for (int i = 0; i < RING_LEDS; i++) ring_set(i, r, g, b);
}

static void ring_clear() {
  for (int i = 0; i < RING_LEDS * 3; i++) ring_frame[i] = 0;
}

// Intermittent buzzer: the request (from Python) raises g_buzzer_on and the PWM
// is switched on/off in pulses inside loop().
static volatile int g_buzzer_on = 0;
static unsigned long buzzer_last = 0;
static bool buzzer_phase = false;

static void buzzer_update(unsigned long now) {
  if (g_buzzer_on) {
    unsigned long dur = buzzer_phase ? BUZZER_BEEP_ON_MS : BUZZER_BEEP_OFF_MS;
    if (now - buzzer_last >= dur) {
      buzzer_last = now;
      buzzer_phase = !buzzer_phase;
      analogWrite(PIN_BUZZER, buzzer_phase ? buzzer_duty_value() : 0);
    }
  } else if (buzzer_phase) {
    buzzer_phase = false;
    analogWrite(PIN_BUZZER, 0);
  }
}

// ---------------------------------------------------------------------------
// Autonomous demo flow (provisional) - MCU side
// ---------------------------------------------------------------------------
// Continuous cycle:
//   ALARM    (5 s) : yellow ring blinking with acceleration,
//                    LCD "WARNING! CAR APPROACHING",
//                    intermittent buzzer at 1%.
//   COUNTDOWN(10 s): ring off, buzzer silent, countdown on the display.
// Then it restarts. Ring/buzzer/LCD are driven here (not by the vision state).

#define FLOW_WARN_MS 5000
#define FLOW_WAIT_MS 10000
#define RING_WARN_R 200
#define RING_WARN_G 150
#define RING_WARN_B 0

static bool g_flow_active = false;  // idle until Python commands effects or enables the demo
static bool flow_init = false;
static unsigned long flow_start = 0;
static unsigned long flow_last_ms = 0;
static unsigned long flow_lcd_last = 0;
static float flow_blink_phase = 0.0f;
static bool flow_ring_on = false;
static bool flow_ring_lit = false;
static int flow_msg_off = 0;

// 16-character window of a scrolling message (marquee).
static String marquee16(const char *msg, int off) {
  int len = (int)strlen(msg);
  String out;
  for (int i = 0; i < LCD_COLS; i++) {
    int idx = off + i;
    out += (idx < len) ? (char)msg[idx] : ' ';
  }
  return out;
}

static void flow_update(unsigned long now) {
  if (!g_flow_active) return;
  if (!flow_init) {
    flow_init = true;
    flow_start = now;
    flow_last_ms = now;
    flow_blink_phase = 0.0f;
    flow_ring_on = true;
    flow_ring_lit = false;
  }

  unsigned long dt = now - flow_last_ms;
  flow_last_ms = now;
  unsigned long elapsed = now - flow_start;

  if (elapsed < FLOW_WARN_MS) {
    // ---------------- ALARM (5 s) ----------------
    // Blink with acceleration: half-period going from 250 ms to 60 ms.
    float half = 250.0f - 190.0f * (float)elapsed / (float)FLOW_WARN_MS;
    if (dt > 0) flow_blink_phase += (float)dt / half;
    if (flow_blink_phase >= 1.0f) {
      flow_blink_phase -= 1.0f;
      flow_ring_on = !flow_ring_on;
    }

    if (flow_ring_on != flow_ring_lit) {
      flow_ring_lit = flow_ring_on;
      if (flow_ring_on) ring_fill(RING_WARN_R, RING_WARN_G, RING_WARN_B);
      else ring_clear();
      ring_send();
    }

    g_buzzer_on = 1;  // continuous intermittent beep (1%)
    buzzer_update(now);

    // LCD: fixed "WARNING!" + scrolling "CAR APPROACHING".
    if (now - flow_lcd_last >= 350) {
      flow_lcd_last = now;
      static const char *msg = "CAR APPROACHING    ";
      lcd_print_line(0, "WARNING!");
      lcd_print_line(1, marquee16(msg, flow_msg_off));
      flow_msg_off++;
      if (flow_msg_off > (int)strlen(msg)) flow_msg_off = 0;
    }
  } else {
    // ---------------- COUNTDOWN (10 s) ----------------
    if (flow_ring_lit) {
      flow_ring_lit = false;
      flow_ring_on = false;
      ring_clear();
      ring_send();
    }
    g_buzzer_on = 0;
    buzzer_update(now);

    unsigned long remain = FLOW_WARN_MS + FLOW_WAIT_MS - elapsed;
    unsigned long secs = (remain + 999) / 1000;
    if (now - flow_lcd_last >= 500) {
      flow_lcd_last = now;
      lcd_print_line(0, "NEXT CYCLE");
      lcd_print_line(1, String("IN ") + String(secs) + " s");
    }

    if (elapsed >= FLOW_WARN_MS + FLOW_WAIT_MS) {
      flow_start = now;
      flow_blink_phase = 0.0f;
      flow_ring_on = true;
      flow_msg_off = 0;
      flow_lcd_last = 0;  // force a refresh
    }
  }
}

// ---------------------------------------------------------------------------
// Effects engine controllable from Python (ring / buzzer / LCD)
// ---------------------------------------------------------------------------
// Exposes simple RPCs. Any fx_* command automatically disables the
// autonomous flow, so Python takes control of the actuators; set_flow(1)
// re-enables the flow.

enum {
  RING_FX_OFF = 0,
  RING_FX_SOLID = 1,
  RING_FX_BLINK = 2,
  RING_FX_SPINNER = 3,
};

static int fx_ring_mode = RING_FX_OFF;
static uint8_t fx_ring_r = 0, fx_ring_g = 0, fx_ring_b = 0;
static unsigned long fx_ring_period = 500;
static unsigned long fx_ring_last = 0;
static bool fx_ring_dirty = true;
static bool fx_ring_blink_on = false;
static uint8_t fx_ring_pos = 0;

static bool fx_buz_active = false;
static int fx_buz_on_ms = 200;
static int fx_buz_off_ms = 300;
static int fx_buz_reps = 0;  // 0 = infinite
static int fx_buz_duty = BUZZER_DUTY_PCT;
static int fx_buz_done = 0;
static bool fx_buz_phase = false;
static unsigned long fx_buz_last = 0;

static int duty_pct_to_value(int pct) {
  if (pct < 0) pct = 0;
  if (pct > 100) pct = 100;
  return ((1 << BUZZER_PWM_BITS) - 1) * pct / 100;
}

static void ring_spinner_frame(uint8_t r, uint8_t g, uint8_t b, uint8_t pos) {
  static const uint8_t tail[6] = {255, 160, 90, 45, 18, 6};
  for (int i = 0; i < RING_LEDS; i++) {
    int d = (pos - i + RING_LEDS) % RING_LEDS;
    uint8_t level = (d < 6) ? tail[d] : 0;
    ring_set(i, (uint16_t)r * level / 255, (uint16_t)g * level / 255,
             (uint16_t)b * level / 255);
  }
}

static void fx_ring_update(unsigned long now) {
  if (g_flow_active) return;
  switch (fx_ring_mode) {
    case RING_FX_OFF:
      if (fx_ring_dirty) {
        fx_ring_dirty = false;
        ring_clear();
        ring_send();
      }
      break;
    case RING_FX_SOLID:
      if (fx_ring_dirty) {
        fx_ring_dirty = false;
        ring_fill(fx_ring_r, fx_ring_g, fx_ring_b);
        ring_send();
      }
      break;
    case RING_FX_BLINK:
      if (now - fx_ring_last >= fx_ring_period / 2) {
        fx_ring_last = now;
        fx_ring_blink_on = !fx_ring_blink_on;
        if (fx_ring_blink_on) ring_fill(fx_ring_r, fx_ring_g, fx_ring_b);
        else ring_clear();
        ring_send();
      }
      break;
    case RING_FX_SPINNER:
      if (now - fx_ring_last >= fx_ring_period) {
        fx_ring_last = now;
        ring_spinner_frame(fx_ring_r, fx_ring_g, fx_ring_b, fx_ring_pos);
        ring_send();
        fx_ring_pos = (fx_ring_pos + 1) % RING_LEDS;
      }
      break;
  }
}

static void fx_buzzer_update(unsigned long now) {
  if (g_flow_active || !fx_buz_active) return;
  unsigned long dur =
      fx_buz_phase ? (unsigned long)fx_buz_on_ms : (unsigned long)fx_buz_off_ms;
  if (now - fx_buz_last >= dur) {
    fx_buz_last = now;
    fx_buz_phase = !fx_buz_phase;
    if (fx_buz_phase) {
      analogWrite(PIN_BUZZER, duty_pct_to_value(fx_buz_duty));
    } else {
      analogWrite(PIN_BUZZER, 0);
      fx_buz_done++;
      if (fx_buz_reps > 0 && fx_buz_done >= fx_buz_reps) {
        fx_buz_active = false;
      }
    }
  }
}

// --- Effects RPC (Python -> MCU) ---

static void take_manual_control() {
  if (!g_flow_active) return;
  g_flow_active = false;
  g_buzzer_on = 0;
  buzzer_phase = false;
  analogWrite(PIN_BUZZER, 0);
  // Clear a frame left by the autonomous flow before manual updates resume.
  ring_clear();
  ring_send();
  fx_ring_dirty = true;
}


static void apply_flow(int on) {
  if (on) {
    g_flow_active = true;
    flow_init = false;  // restart the cycle
    fx_ring_mode = RING_FX_OFF;
    fx_buz_active = false;
    analogWrite(PIN_BUZZER, 0);
  } else {
    take_manual_control();
  }
}

static void apply_ring(int mode, int r, int g, int b, int period_ms) {
  take_manual_control();
  unsigned long period = period_ms > 0 ? (unsigned long)period_ms : 500;
  if (fx_ring_mode == mode && fx_ring_r == r && fx_ring_g == g &&
      fx_ring_b == b && fx_ring_period == period) return;
  bool keep_position = mode == RING_FX_SPINNER;
  fx_ring_mode = mode;
  fx_ring_r = (uint8_t)constrain(r, 0, 255);
  fx_ring_g = (uint8_t)constrain(g, 0, 255);
  fx_ring_b = (uint8_t)constrain(b, 0, 255);
  fx_ring_period = period_ms > 0 ? (unsigned long)period_ms : 500;
  fx_ring_dirty = true;
  fx_ring_blink_on = false;
  if (!keep_position && mode == RING_FX_OFF) fx_ring_pos = 0;
  fx_ring_last = millis();
}

static void apply_buzzer(int on_ms, int off_ms, int reps, int duty_pct) {
  take_manual_control();
  fx_buz_on_ms = on_ms > 0 ? on_ms : 200;
  fx_buz_off_ms = off_ms > 0 ? off_ms : 300;
  fx_buz_reps = reps < 0 ? 0 : reps;
  fx_buz_duty = (duty_pct >= 0 && duty_pct <= 100) ? duty_pct : BUZZER_DUTY_PCT;
  fx_buz_done = 0;
  fx_buz_phase = true;  // starts immediately with the tone
  fx_buz_active = true;
  fx_buz_last = millis();
  analogWrite(PIN_BUZZER, duty_pct_to_value(fx_buz_duty));
}

static void apply_buzzer_off() {
  take_manual_control();
  fx_buz_active = false;
  analogWrite(PIN_BUZZER, 0);
}

static void apply_lcd(const char *line1, const char *line2) {
  take_manual_control();
  static String last_line1, last_line2;
  static bool initialized = false;
  if (!initialized || last_line1 != line1) lcd_print_line(0, line1);
  if (!initialized || last_line2 != line2) lcd_print_line(1, line2);
  last_line1 = line1;
  last_line2 = line2;
  initialized = true;
}

// Bridge runs callbacks on its own thread. Only loop() touches hardware.
K_MUTEX_DEFINE(effects_mailbox_mutex);
struct EffectsMailbox {
  bool ring_pending = false, lcd_pending = false;
  bool buzzer_pending = false, buzzer_off_pending = false, flow_pending = false;
  int mode, r, g, b, period, on_ms, off_ms, reps, duty, flow;
  char line1[LCD_COLS + 1] = {}, line2[LCD_COLS + 1] = {};
};
static EffectsMailbox mailbox;

void set_flow(int on) {
  k_mutex_lock(&effects_mailbox_mutex, K_FOREVER);
  mailbox.flow = on;
  mailbox.flow_pending = true;
  k_mutex_unlock(&effects_mailbox_mutex);
}

void fx_ring(int mode, int r, int g, int b, int period_ms) {
  k_mutex_lock(&effects_mailbox_mutex, K_FOREVER);
  mailbox.mode = mode;
  mailbox.r = constrain(r, 0, 255);
  mailbox.g = constrain(g, 0, 255);
  mailbox.b = constrain(b, 0, 255);
  mailbox.period = period_ms;
  mailbox.ring_pending = true;
  k_mutex_unlock(&effects_mailbox_mutex);
}
void fx_ring_off() { fx_ring(RING_FX_OFF, 0, 0, 0, 0); }

void fx_buzzer(int on_ms, int off_ms, int reps, int duty_pct) {
  k_mutex_lock(&effects_mailbox_mutex, K_FOREVER);
  mailbox.on_ms = on_ms; mailbox.off_ms = off_ms;
  mailbox.reps = reps; mailbox.duty = duty_pct;
  mailbox.buzzer_pending = true;
  mailbox.buzzer_off_pending = false;
  k_mutex_unlock(&effects_mailbox_mutex);
}
void fx_buzzer_off() {
  k_mutex_lock(&effects_mailbox_mutex, K_FOREVER);
  mailbox.buzzer_off_pending = true;
  mailbox.buzzer_pending = false;
  k_mutex_unlock(&effects_mailbox_mutex);
}

void fx_lcd(String line1, String line2) {
  k_mutex_lock(&effects_mailbox_mutex, K_FOREVER);
  line1.toCharArray(mailbox.line1, sizeof(mailbox.line1));
  line2.toCharArray(mailbox.line2, sizeof(mailbox.line2));
  mailbox.lcd_pending = true;
  k_mutex_unlock(&effects_mailbox_mutex);
}
void fx_lcd_clear() { fx_lcd("", ""); }

static void apply_pending_effects() {
  k_mutex_lock(&effects_mailbox_mutex, K_FOREVER);
  EffectsMailbox pending = mailbox;
  mailbox.ring_pending = mailbox.lcd_pending = false;
  mailbox.buzzer_pending = mailbox.buzzer_off_pending = mailbox.flow_pending = false;
  k_mutex_unlock(&effects_mailbox_mutex);
  if (pending.flow_pending) apply_flow(pending.flow);
  if (pending.ring_pending) apply_ring(pending.mode, pending.r, pending.g, pending.b, pending.period);
  if (pending.buzzer_pending) apply_buzzer(pending.on_ms, pending.off_ms, pending.reps, pending.duty);
  if (pending.buzzer_off_pending) apply_buzzer_off();
  if (pending.lcd_pending) apply_lcd(pending.line1, pending.line2);
}

// Diagnostics: LCD bus (0 absent, 1 header, 2 Qwiic), ring call timing (ns).
int lcd_status() { return g_lcd_bus_id; }
int ring_status() { return (int)(ring_call_us * 1000.0f); }
int ring_frames() { return (int)ring_frame_count; }
int lcd_errors() { return (int)lcd_error_count; }

void setup() {
  pinMode(PIN_BUZZER, OUTPUT);
  analogWriteResolution(BUZZER_PWM_BITS);
  analogWrite(PIN_BUZZER, 0);
  if (lcd_begin()) {
    lcd_print_line(0, "LARP CROSSWALK");
    lcd_print_line(1, "READY");
  }
  ring_begin();
  ring_clear();
  ring_send();

  Bridge.begin();
  Bridge.provide("lcd_status", lcd_status);
  Bridge.provide("ring_status", ring_status);
  Bridge.provide("ring_frames", ring_frames);
  Bridge.provide("lcd_errors", lcd_errors);
  Bridge.provide("set_flow", set_flow);
  Bridge.provide("fx_ring", fx_ring);
  Bridge.provide("fx_ring_off", fx_ring_off);
  Bridge.provide("fx_buzzer", fx_buzzer);
  Bridge.provide("fx_buzzer_off", fx_buzzer_off);
  Bridge.provide("fx_lcd", fx_lcd);
  Bridge.provide("fx_lcd_clear", fx_lcd_clear);
}

void loop() {
  apply_pending_effects();
  unsigned long now = millis();
  if (g_flow_active) {
    flow_update(now);
  } else {
    fx_ring_update(now);
    fx_buzzer_update(now);
  }
}
