"""High-level interface to drive the MCU actuators from Python.

It lets you trigger effects on:
  * RGB ring (16x WS2813, pin D6)    -> solid, blink, spinner
  * passive buzzer (pin D5)          -> intermittent beeps, volume via duty
  * 16x2 LCD display (I2C)           -> two lines of text

Everything goes through the Bridge (RPC to the sketch on the STM32). Sending an
``fx_*`` command automatically disables the MCU's autonomous flow: from then on
Python drives the actuators. ``fx.flow(True)`` returns to the flow.

Example::

    from effects import Effects
    fx = Effects()

    fx.ring_spinner("cyan", 90)
    fx.ring_blink("yellow", period_ms=400)
    fx.ring_solid((255, 200, 0))
    fx.beep(on_ms=200, off_ms=300, reps=3)      # 3 beeps
    fx.buzzer(on_ms=200, off_ms=300)            # continuous intermittent
    fx.lcd("WARNING!", "CAR APPROACHING")
    ...
    fx.all_off()                                # ring + buzzer + lcd off

Colors can be given as a name ("yellow", "cyan", ...), an (r, g, b) tuple,
or an 0xRRGGBB integer.
"""

from __future__ import annotations

from arduino.app_utils import Bridge

# Ready-to-use colors (r, g, b).
COLORS: dict[str, tuple[int, int, int]] = {
    "off": (0, 0, 0),
    "red": (255, 0, 0),
    "green": (0, 255, 0),
    "blue": (0, 0, 255),
    "yellow": (255, 200, 0),
    "amber": (255, 150, 0),
    "orange": (255, 120, 0),
    "cyan": (0, 180, 220),
    "white": (255, 255, 255),
    "purple": (160, 0, 255),
    "magenta": (255, 0, 180),
}


def to_rgb(color) -> tuple[int, int, int]:
    """Normalize a color to (r, g, b) 0-255.

    Accepts: color name, (r, g, b) tuple/list, 0xRRGGBB integer.
    """
    if isinstance(color, str):
        return COLORS.get(color.strip().lower(), (255, 255, 255))
    if isinstance(color, int):
        return ((color >> 16) & 0xFF, (color >> 8) & 0xFF, color & 0xFF)
    if isinstance(color, (tuple, list)) and len(color) == 3:
        return tuple(max(0, min(255, int(c))) for c in color)  # type: ignore[return-value]
    return (255, 255, 255)


class Effects:
    """RPC wrapper for the MCU effects engine.

    The RING_* constants must match the sketch.
    """

    RING_OFF = 0
    RING_SOLID = 1
    RING_BLINK = 2
    RING_SPINNER = 3

    def __init__(self, default_duty_pct: int = 1) -> None:
        # Default buzzer volume (percentage of PWM full scale).
        self.default_duty_pct = int(default_duty_pct)

    # ------------------------------------------------------------------ ring
    def _ring(self, mode: int, color, period_ms: int = 0) -> None:
        r, g, b = to_rgb(color)
        Bridge.call("fx_ring", int(mode), r, g, b, int(period_ms), timeout=2)

    def ring_off(self) -> None:
        """Turn the ring off."""
        Bridge.notify("fx_ring_off")

    def ring_solid(self, color="white") -> None:
        """Ring lit solid in one color."""
        self._ring(self.RING_SOLID, color, 0)

    def ring_blink(self, color="yellow", period_ms: int = 500) -> None:
        """Blinking ring (period_ms = duration of one on+off cycle)."""
        self._ring(self.RING_BLINK, color, period_ms)

    def ring_spinner(self, color="cyan", period_ms: int = 90) -> None:
        """Rotating spinner (comet); period_ms = time per LED step."""
        self._ring(self.RING_SPINNER, color, period_ms)

    def ring(self, mode: str, color="white", period_ms: int = 500) -> None:
        """Generic API: mode in {'off','solid','blink','spinner'}."""
        modes = {
            "off": self.RING_OFF,
            "solid": self.RING_SOLID,
            "blink": self.RING_BLINK,
            "spinner": self.RING_SPINNER,
        }
        m = modes.get(str(mode).strip().lower())
        if m is None:
            raise ValueError(f"unknown ring mode: {mode!r}")
        self._ring(m, color, period_ms)

    # ---------------------------------------------------------------- buzzer
    def beep(
        self,
        on_ms: int = 200,
        off_ms: int = 300,
        reps: int = 1,
        duty_pct: int | None = None,
    ) -> None:
        """Intermittent beeps.

        reps=0  -> continuous until you call :meth:`buzzer_off`.
        duty_pct -> volume (percentage of PWM full scale); default 1%.
        """
        duty = self.default_duty_pct if duty_pct is None else int(duty_pct)
        Bridge.call("fx_buzzer", int(on_ms), int(off_ms), int(reps), duty, timeout=2)

    def buzzer(self, on_ms: int = 200, off_ms: int = 300,
               duty_pct: int | None = None) -> None:
        """Continuous intermittent buzzer (until :meth:`buzzer_off`)."""
        self.beep(on_ms, off_ms, 0, duty_pct)

    def buzzer_off(self) -> None:
        """Silence the buzzer."""
        Bridge.notify("fx_buzzer_off")

    # ------------------------------------------------------------------- lcd
    def lcd(self, line1: str, line2: str = "") -> None:
        """Write two lines (max 16 characters each)."""
        Bridge.call("fx_lcd", str(line1)[:16], str(line2)[:16], timeout=2)

    def lcd_clear(self) -> None:
        """Clear the display."""
        Bridge.notify("fx_lcd_clear")

    # ------------------------------------------------------------------ flow
    def flow(self, on: bool = True) -> None:
        """Re-enable (True) or stop (False) the MCU's autonomous flow."""
        Bridge.notify("set_flow", 1 if on else 0)

    # ------------------------------------------------------------- composites
    def alert(self, line1: str = "WARNING!", line2: str = "CAR APPROACHING") -> None:
        """Alarm scenario: blinking yellow ring + buzzer + message."""
        self.ring_blink("yellow", 300)
        self.buzzer(200, 300)
        self.lcd(line1, line2)

    def all_off(self) -> None:
        """Turn off ring, buzzer and display."""
        self.ring_off()
        self.buzzer_off()
        self.lcd_clear()


# Ready-to-use instance: ``from effects import fx``.
fx = Effects()

__all__ = ["Effects", "fx", "COLORS", "to_rgb"]
