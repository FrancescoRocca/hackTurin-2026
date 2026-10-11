"""Demo of the `effects` interface (ring + buzzer + LCD).

The app does not run it: launch it by hand to try the effects, e.g.
inside the container::

    python /app/python/effects_demo.py
"""

import time

from effects import Effects

fx = Effects()


def main() -> None:
    fx.flow(False)  # Python takes control (stops the autonomous flow)
    print("1) solid red ring + LCD")
    fx.ring_solid("red")
    fx.lcd("SENTINELLA", "EFFECTS TEST")
    time.sleep(2)

    print("2) blinking yellow ring (slow -> fast)")
    for period in (600, 400, 250):
        fx.ring_blink("yellow", period)
        time.sleep(2)

    print("3) cyan spinner")
    fx.ring_spinner("cyan", 80)
    time.sleep(3)

    print("4) alarm: yellow + 3 beeps + message")
    fx.alert()
    time.sleep(0.2)
    fx.buzzer_off()
    fx.beep(200, 300, 3)
    time.sleep(2)

    print("5) everything off")
    fx.all_off()


if __name__ == "__main__":
    main()
