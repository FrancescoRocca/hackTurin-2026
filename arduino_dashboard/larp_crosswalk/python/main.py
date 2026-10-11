# SPDX-FileCopyrightText: Copyright (C) Arduino s.r.l. and/or its affiliated companies
#
# SPDX-License-Identifier: MPL-2.0

from io import BytesIO
import json
import os

from PIL import Image
import cv2
import requests
from fastapi import Request
from fastapi.responses import Response
from arduino.app_utils import App, brick
from arduino.app_bricks.dbstorage_sqlstore import SQLStore
from arduino.app_bricks.object_detection import ObjectDetection
from arduino.app_bricks.web_ui import WebUI
from arduino.app_peripherals.camera import Camera
from camera_pipeline import CameraPipeline
from effects import fx
from output_controller import OutputController
from object_tracker import ObjectTracker
from detection_storage import DetectionStorage
from telemetry_sync import TelemetrySync, load_config

CAMERA_SOURCE = os.getenv("CAMERA_SOURCE", "csi:CAMERA0")
DETECTION_FRAME_INTERVAL = 2


@brick
class VisionWorkers:
    """Stop inference/sync before App Lab closes the SQLStore brick."""
    def __init__(self, pipeline, sync):
        self.pipeline = pipeline
        self.sync = sync

    def start(self):
        self.sync.start()
        self.pipeline.start()

    def stop(self):
        self.pipeline.stop()
        self.sync.stop()


def fresh_detections(metadata):
    fresh = (
        metadata["status"] == "live"
        and metadata["detection_age_ms"] is not None
        and metadata["detection_age_ms"] <= 1500
    )
    return metadata["detections"] if fresh else []


def ring_color(metadata):
    people = [
        float(item["confidence"])
        for item in fresh_detections(metadata)
        if item.get("class_name", "").strip().casefold() == "person"
    ]
    if not people:
        return "green"
    return "red" if max(people) > 75 else "yellow"


def lcd_lines(metadata):
    names = {
        "car": "CAR",
        "motorcycle": "MOTORBIKE",
        "motorbike": "MOTORBIKE",
        "bicycle": "BICYCLE",
        "bike": "BICYCLE",
    }
    vehicles = [
        item for item in fresh_detections(metadata)
        if item.get("class_name", "").strip().casefold() in names
    ]
    if not vehicles:
        return "LARP CROSSWALK", ""
    vehicle = max(vehicles, key=lambda item: float(item["confidence"]))
    return names[vehicle["class_name"].strip().casefold()], "APPROACHING"


def main():
    camera = Camera(
        CAMERA_SOURCE, resolution=(640, 640), fps=60,
    )
    camera.first_connection_max_retries = 3
    pipeline = None
    workers = None
    session = requests.Session()
    try:
        db = SQLStore("detections.db")
        storage = DetectionStorage(db, camera_name=load_config()["camera_name"])
        tracker = ObjectTracker()
        sync = TelemetrySync(storage)
        camera.start()
        detector = ObjectDetection()

        def infer(frame):
            # The installed image API requires PNG/JPEG. PNG level 0 avoids
            # JPEG and compression work, stays in memory, and preserves pixels.
            buffer = BytesIO()
            Image.frombytes("RGB", (frame.width, frame.height), frame.rgb).save(
                buffer, format="PNG", compress_level=0
            )
            response = session.post(
                f"{detector.url}/api/image",
                files={"file": ("frame.png", buffer.getvalue(), "image/png")},
                timeout=(2, 10),
            )
            response.raise_for_status()
            return detector._extract_detection(response.json())

        def log_detections(frame, output):
            events = tracker.update(output.get("detection", []), frame.captured_at,
                                    frame.width, frame.height, frame.generation)
            storage.record(events)

        pipeline = CameraPipeline(camera, infer, interval=DETECTION_FRAME_INTERVAL,
                                  on_detection=log_detections)
        ui = WebUI()

        def preview():
            _, metadata = pipeline.snapshot()
            return {**metadata, "source": CAMERA_SOURCE}

        def raw_frame(since: int = 0):
            frame, metadata = pipeline.snapshot()
            metadata["source"] = CAMERA_SOURCE
            headers = {
                "Cache-Control": "no-store",
                "X-Frame-Meta": json.dumps(metadata, separators=(",", ":"), ensure_ascii=True),
            }
            if frame is None or frame.sequence == since:
                return Response(status_code=204, headers=headers)
            return Response(content=frame.rgb, media_type="application/octet-stream", headers=headers)

        ui.expose_api("GET", "/api/preview", preview)
        ui.expose_api("GET", "/api/frame", raw_frame)
        ui.expose_api("GET", "/api/stats", sync.status)

        def clear_board_database(request: Request):
            if (request.headers.get("X-Confirm-Local-Reset") != "delete-board-data"
                    or request.headers.get("Sec-Fetch-Site") == "cross-site"):
                return Response(status_code=403)
            return sync.clear_local()

        ui.expose_api("POST", "/api/stats/clear-local", clear_board_database)
        # Registered after SQLStore, so reverse-order shutdown stops workers first.
        workers = VisionWorkers(pipeline, sync)
        print("CAMERA0 capture and inference run independently; raw RGB preview; no snapshots.", flush=True)
        outputs = OutputController(fx)

        def loop():
            if pipeline.error:
                raise RuntimeError(pipeline.error)
            _, metadata = pipeline.snapshot()
            outputs.update(ring_color(metadata), lcd_lines(metadata))
            pipeline.stopping.wait(0.1)

        App.run(user_loop=loop)
    finally:
        if workers is not None:
            workers.stop()
        elif pipeline is not None:
            pipeline.stop()
        camera.stop()
        session.close()


if __name__ == "__main__":
    main()
