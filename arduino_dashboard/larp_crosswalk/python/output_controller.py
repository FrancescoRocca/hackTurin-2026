"""Stabilize detection-driven outputs and retry unacknowledged Bridge calls."""
import time


class StableValue:
    def __init__(self):
        self.value = None
        self.candidate = None
        self.since = 0

    def update(self, desired, now, delay):
        if desired != self.candidate:
            self.candidate = desired
            self.since = now
        if self.value is None or now - self.since >= delay:
            self.value = desired
        return self.value


class OutputController:
    def __init__(self, effects):
        self.effects = effects
        self.ring = StableValue()
        self.lcd = StableValue()
        self.sent = {}
        self.refresh_at = {}
        self.retry_at = {}
        self.beep_for = None
        self.beep_retry_at = 0

    def _send(self, key, value, now, action):
        if now < self.retry_at.get(key, 0):
            return
        if self.sent.get(key) == value and now < self.refresh_at.get(key, 0):
            return
        try:
            action()
        except Exception as exc:
            print(f"{key} Bridge command failed; retrying: {exc}", flush=True)
            self.retry_at[key] = now + 1
            return
        if self.sent.get(key) != value:
            print(f"{key}: {value}", flush=True)
        self.sent[key] = value
        self.refresh_at[key] = now + 2

    def update(self, color, lines, now=None):
        now = time.monotonic() if now is None else now
        # Red is immediate. Require sustained absence before returning to green.
        color = self.ring.update(color, now, {"red": 0, "yellow": 0.25, "green": 0.6}[color])
        lines = self.lcd.update(lines, now, 0.8 if lines[0] == "LARP CROSSWALK" else 0.25)
        self._send("Ring", color, now, lambda: (
            self.effects.ring_spinner("green", period_ms=90)
            if color == "green" else self.effects.ring_solid(color)
        ))
        self._send("LCD", lines, now, lambda: self.effects.lcd(*lines))
        # Announce only an acknowledged change to a vehicle warning, not refreshes.
        if self.sent.get("LCD") == lines:
            if lines[1] != "APPROACHING":
                self.beep_for = None
            elif self.beep_for != lines and now >= self.beep_retry_at:
                try:
                    self.effects.beep(on_ms=500, off_ms=300, reps=1, duty_pct=50)
                except Exception as exc:
                    print(f"Buzzer Bridge command failed; retrying: {exc}", flush=True)
                    self.beep_retry_at = now + 1
                else:
                    self.beep_for = lines
                    print(f"Buzzer: {lines[0]} warning", flush=True)
