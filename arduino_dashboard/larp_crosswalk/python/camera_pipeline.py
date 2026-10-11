"""Capture and infer independently, retaining only the newest frame/result."""
from dataclasses import dataclass
import threading
import time

import cv2


@dataclass(frozen=True)
class Frame:
    sequence: int
    generation: int
    captured_at: float
    width: int
    height: int
    rgb: bytes


class CameraPipeline:
    def __init__(self, camera, detector, interval=2, on_detection=None):
        self.camera = camera
        self.detector = detector
        self.interval = interval
        self.on_detection = on_detection
        self.condition = threading.Condition()
        self.stopping = threading.Event()
        self.frame = None
        self.result = None
        self.camera_available = False
        self.error = None
        self.generation = 0
        self.threads = []
        self.capture_count = 0
        self.inference_count = 0
        self.started_at = time.monotonic()

    def start(self):
        self.started_at = time.monotonic()
        for name, target in (("CameraCapture", self._capture), ("ModelInference", self._infer)):
            thread = threading.Thread(name=name, target=self._guard, args=(target,), daemon=True)
            self.threads.append(thread)
            thread.start()

    def _guard(self, target):
        try:
            target()
        except Exception as exc:
            with self.condition:
                self.error = f"{threading.current_thread().name}: {exc}"
                self.stopping.set()
                self.condition.notify_all()

    def _capture(self):
        while not self.stopping.is_set():
            bgr = self.camera.capture()
            if bgr is None:
                with self.condition:
                    if self.camera_available:
                        self.generation += 1
                    self.camera_available = False
                    self.result = None
                    self.condition.notify_all()
                self.stopping.wait(0.05)
                continue
            captured_at = time.monotonic()
            # No codec: publish immutable RGB bytes directly to the browser.
            rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
            height, width = rgb.shape[:2]
            pixels = rgb.tobytes()
            with self.condition:
                self.capture_count += 1
                self.frame = Frame(self.capture_count, self.generation, captured_at, width, height, pixels)
                self.camera_available = True
                self.condition.notify_all()

    def _infer(self):
        last_sequence = -self.interval
        last_generation = -1
        while not self.stopping.is_set():
            with self.condition:
                self.condition.wait_for(lambda: self.stopping.is_set() or (
                    self.camera_available and self.frame is not None and (
                        self.frame.generation != last_generation or
                        self.frame.sequence >= last_sequence + self.interval
                    )
                ))
                if self.stopping.is_set():
                    return
                # Take the latest frame at the moment this worker becomes free.
                frame = self.frame
            started = time.monotonic()
            output = self.detector(frame)
            inference_ms = round((time.monotonic() - started) * 1000)
            if output is None:
                raise RuntimeError("Model runner returned no detection result")
            accepted = False
            with self.condition:
                self.inference_count += 1
                last_sequence = frame.sequence
                last_generation = frame.generation
                # Discard in-flight results from before a camera interruption.
                if self.camera_available and frame.generation == self.generation:
                    self.result = {
                        "detections": output.get("detection", []),
                        "detection_sequence": frame.sequence,
                        "detection_captured_at": frame.captured_at,
                        "inference_ms": inference_ms,
                    }
                    accepted = True
            # Exactly once per accepted inference, outside the camera condition.
            # This avoids losing results when hardware RPCs delay the UI loop.
            if accepted and self.on_detection is not None:
                self.on_detection(frame, output)

    def snapshot(self):
        with self.condition:
            frame, result = self.frame, self.result
            available, error = self.camera_available, self.error
            captures, inferences = self.capture_count, self.inference_count
        now = time.monotonic()
        elapsed = max(now - self.started_at, 0.001)
        meta = {
            "status": "error" if error else "waiting" if frame is None else
                "live" if available and now - frame.captured_at < 2 else "stale",
            "error": error,
            "sequence": frame.sequence if frame else 0,
            "width": frame.width if frame else 640,
            "height": frame.height if frame else 480,
            "age_sec": round(now - frame.captured_at, 3) if frame else None,
            "detections": result["detections"] if result else [],
            "inference_ms": result["inference_ms"] if result else None,
            "detection_sequence": result["detection_sequence"] if result else None,
            "detection_age_ms": round((now - result["detection_captured_at"]) * 1000) if result else None,
            "capture_count": captures,
            "inference_count": inferences,
            "capture_fps": round(captures / elapsed, 1),
            "detection_fps": round(inferences / elapsed, 1),
            "pixel_format": "RGB24",
        }
        return frame, meta

    def stop(self):
        self.stopping.set()
        with self.condition:
            self.condition.notify_all()
        for thread in self.threads:
            thread.join(timeout=12)
