# larp_crosswalk

Arduino UNO Q App Lab app combining the **Prova vision pipeline** and the
**Sentinel effects module**. The ring rotates green by default, turns solid red
for a person above 75% confidence, and solid yellow for a person at 75% or below.
The original apps are unchanged.

Open this folder in Arduino App Lab and press **Run**. The manifest retains
Prova's `arduino:web_ui` and `arduino:object_detection` bricks with model
`ei-model-1135661-1`. Preview: `http://<board-ip>:7000`.

## Included

- `python/main.py`: Prova's camera, model-service inference, preview APIs, and
  app lifecycle; imports `fx` ready for use.
- `python/camera_pipeline.py`: unchanged threaded capture/inference pipeline.
- `assets/`: Prova's live RGB preview and detection overlay.
- `python/effects.py`: importable ring, buzzer and LCD API.
- `python/effects_demo.py`: optional finite effects sequence, run in the app's
  Python environment using `python /app/python/effects_demo.py`.
- `sketch/`: matching effects RPC engine, LCD bus detection and WS2813 driver.

The camera defaults to `csi:CAMERA0`, **640 x 640 at a requested 60 FPS**,
with an inference interval of two captured frames, matching Prova's actual
Python settings. These are requested settings, not measured throughput.
Frames are flipped vertically before preview and inference, keeping detection
coordinates aligned with the displayed image.
Override the source using `CAMERA_SOURCE` in the runtime environment.
Capture and inference run independently, keep the newest frame/result, and
publish RGB24 preview frames. Inference uploads uncompressed PNGs in memory.

## Effects

Wire the 16-LED WS2813 ring to **D6**, passive buzzer to **D5**, and Grove
16x2 RGB LCD to **Qwiic/Wire1** or **SDA/SCL D20/D21/Wire**.
When the Python app starts, the ring rotates green (90 ms per LED step).
Fresh `person` detections turn it solid red if any confidence is above 75%,
otherwise solid yellow. Exactly 75% is yellow. The model's existing detection
confidence filter still applies. Results with no person, results older than
1.5 seconds, or an unavailable camera return it to rotating green.
Red activates immediately. Yellow requires 250 ms of consistent detections;
returning to green requires 600 ms of consistent absence.
The LCD normally shows `LARP CROSSWALK` with a blank second line. Fresh car,
motorcycle or bicycle detections show `CAR`, `MOTORBIKE` or `BICYCLE` on the first
line and `APPROACHING` on the second. If multiple vehicles are detected, the
one with the highest confidence is displayed. No vehicle or stale detections
restore the default text. A vehicle label must persist for 250 ms; returning
to the default text requires 800 ms, reducing flicker from intermittent boxes.
The autonomous demo is disabled by default.

Each newly displayed `CAR`, `MOTORBIKE` or `BICYCLE` / `APPROACHING` warning triggers
one 500 ms beep at 50% PWM duty. Display refreshes and
repeated detection frames do not retrigger it. A different vehicle warning,
or a warning appearing after the default text returns, triggers a new beep.
Buzzer commands are acknowledged and failures are retried after one second.

Ring and LCD commands use acknowledged Bridge calls, retry failures after
one second, and refresh every two seconds to recover after a controller reset.
Repeated commands keep the spinner position and skip unchanged LCD rows.
Bridge callbacks only enqueue the latest requested settings; the sketch's
main loop owns all hardware writes, preventing concurrent LED/LCD access.
The software LED driver masks interrupts for one pixel at a time and services
UART interrupts between pixels, while keeping thread scheduling locked for the
frame. This reduces interference with serial Bridge reception.
The `ring_frames` and `lcd_errors` RPCs report LED frames sent and LCD I2C
write errors for diagnosis. These counters do not establish physical output.

From Python code in this app:

```python
from effects import fx

fx.ring_blink("yellow", period_ms=400)
fx.beep(on_ms=200, off_ms=300, reps=3)
fx.lcd("WARNING!", "CAR APPROACHING")
fx.all_off()
```

`fx.flow(True)` explicitly starts the original five-second warning plus
ten-second countdown demo. `fx.flow(False)` stops that demo; `fx.all_off()`
clears the outputs. LCD clear removes text and leaves its backlight on.

## Integration point

Detection statistics are stored locally with the Arduino **Database - SQL**
brick and sent through HTTP in hourly batches when an endpoint is configured.
See [TELEMETRY.md](TELEMETRY.md) for tracking behavior, configuration, the
JSON contract, offline retries and database access. Status: `/api/stats`.

The nested `loop()` in `python/main.py` runs while capture and inference workers
operate. Read `pipeline.snapshot()` there to obtain frame metadata, detections,
`detection_sequence`, `detection_age_ms`, and camera status. Use that information
for the future crosswalk controller, and call `fx` when the desired effect
changes. Avoid triggering a fresh beep on every loop iteration.

Person detections control the ring; vehicle detections control the LCD.
Other effects remain available through `fx`.
Physical ring colors still require observation on the connected hardware.

## Licenses

The copied Prova `python/main.py` retains its Arduino MPL-2.0 SPDX notice.
`LICENSE` is the MIT license copied with the Sentinel effects implementation.
