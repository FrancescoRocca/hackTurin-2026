"""Run on UNO Q: python /app/tests/test_telemetry.py (isolated test databases)."""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import sys
import threading
import time
import unittest
import uuid

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "python"))
from arduino.app_bricks.dbstorage_sqlstore import SQLStore
from detection_storage import DetectionStorage
from object_tracker import ObjectTracker
from telemetry_sync import TelemetrySync
from camera_pipeline import CameraPipeline
import numpy as np


def detection(label="person", x=20, confidence=90):
    return {"class_name": label, "confidence": str(confidence), "bounding_box_xyxy": [x, 20, x + 60, 100]}


class TrackingTests(unittest.TestCase):
    def test_every_completed_inference_is_logged_without_ui_polling(self):
        class Camera:
            def capture(self):
                time.sleep(.01)
                return np.zeros((8, 8, 3), dtype=np.uint8)
        def infer(frame):
            time.sleep(.02)
            return {"detection": []}
        logged = []
        pipeline = CameraPipeline(Camera(), infer, on_detection=lambda frame, output: logged.append(frame.sequence))
        pipeline.start()
        try:
            time.sleep(.3)  # Deliberately never poll the pipeline during inference.
        finally:
            pipeline.stop()
        _, metadata = pipeline.snapshot()
        self.assertGreaterEqual(len(logged), 5)
        self.assertEqual(len(logged), metadata["inference_count"])
        self.assertEqual(logged, sorted(set(logged)))

    def test_counts_once_and_handles_short_occlusion(self):
        tracker = ObjectTracker()
        self.assertEqual(tracker.update([detection()], 0, 640, 640), [])
        self.assertEqual(len(tracker.update([detection(x=30)], .4, 640, 640)), 1)
        for n in range(2, 7):
            self.assertEqual(tracker.update([detection(x=20 + 10*n)], n*.4, 640, 640), [])
        tracker.update([], 2.8, 640, 640)
        self.assertEqual(tracker.update([detection(x=100)], 3.2, 640, 640), [])
        tracker.update([], 7, 640, 640)
        self.assertEqual(tracker.update([detection()], 7.4, 640, 640), [])
        self.assertEqual(len(tracker.update([detection()], 7.8, 640, 640)), 1)

    def test_multiple_objects_aliases_and_generation(self):
        tracker = ObjectTracker()
        objects = [detection(x=20), detection(x=400), detection("bike", 200), detection("motorbike", 300)]
        tracker.update(objects, 0, 640, 640)
        events = tracker.update(objects, .4, 640, 640)
        self.assertEqual(sorted(e["class"] for e in events), ["bicycle", "motorcycle", "person", "person"])
        self.assertEqual(len({e["event_id"] for e in events}), 4)
        self.assertEqual(tracker.update(objects, .8, 640, 640), [])
        self.assertEqual(tracker.update(objects, 1.2, 640, 640, generation=1), [])
        self.assertEqual(len(tracker.update(objects, 1.6, 640, 640, generation=1)), 4)

    def test_invalid_boxes_and_one_frame_false_positive(self):
        tracker = ObjectTracker()
        invalid = detection(); invalid["bounding_box_xyxy"] = [0, 0, float("nan"), 20]
        self.assertEqual(tracker.update([invalid, detection("dog"), detection()], 0, 640, 640), [])
        self.assertEqual(tracker.update([], 4, 640, 640), [])
        self.assertEqual(tracker.tracks, {})


class StorageTests(unittest.TestCase):
    def setUp(self):
        self.database_name = "_telemetry_test_" + uuid.uuid4().hex + ".db"
        self.db = SQLStore(self.database_name)
        self.hour = int(time.time() // 3600) * 3600
        self.storage = DetectionStorage(self.db, now=self.hour - 7200)

    def tearDown(self):
        self.db.stop()
        for suffix in ("", "-wal", "-shm"):
            Path("/app/data", self.database_name + suffix).unlink(missing_ok=True)

    def event(self, label="person"):
        return {"event_id": str(uuid.uuid4()), "class": label, "confidence": 90}

    def test_durable_events_identity_and_hourly_boundaries(self):
        event = self.event()
        self.storage.record([event], now=self.hour-7199)
        self.storage.record([event], now=self.hour-7198)  # Duplicate event must not count twice.
        self.storage.record([self.event("car")], now=self.hour-3600)
        self.storage.seal_due(now=self.hour)
        first = self.storage.pending()
        payload = json.loads(first["payload"])
        self.assertEqual(payload["counts"], dict(person=1, car=0, bicycle=0, motorcycle=0))
        self.assertEqual(payload["timestamp"], json.loads(self.db.read("sync_batches", order_by="window_start")[1]["payload"])["since"])
        camera_id = self.storage.camera_uuid
        self.db.stop()
        self.db = SQLStore(self.database_name)
        self.storage = DetectionStorage(self.db)
        self.assertEqual(self.storage.camera_uuid, camera_id)
        self.assertEqual(self.storage.pending()["payload"], first["payload"])
        self.storage.acknowledge(first["batch_id"], now=self.hour)
        second = self.storage.pending()
        self.assertEqual(json.loads(second["payload"])["counts"]["car"], 1)
        self.assertEqual(self.storage.status()["counts_since_last_sync"]["car"], 1)

    def test_frozen_batch_never_changes_after_new_sighting(self):
        self.storage.seal_due(now=self.hour)
        first = self.storage.pending()
        self.storage.record([self.event("bicycle")], now=self.hour+1)
        self.assertEqual(self.storage.pending()["payload"], first["payload"])
        self.assertEqual(self.storage.status()["totals"]["bicycle"], 1)

    def test_clock_rollback_does_not_put_events_in_sealed_batch(self):
        self.storage.seal_due(now=self.hour)
        self.storage.record([self.event("person")], now=self.hour-10)
        self.assertEqual(self.storage.status()["counts_since_last_sync"]["person"], 1)
        current = self.storage._counts(self.hour, self.hour+3600)
        self.assertEqual(current["person"], 1)

    def test_clear_only_local_history_preserves_identity_and_resumes(self):
        self.storage.record([self.event()], now=self.hour-7199)
        self.storage.seal_due(now=self.hour)
        identity = self.storage.camera_uuid
        class NoNetwork:
            def post(self, *args, **kwargs):
                raise AssertionError("Local reset must never contact a server")
        sync = TelemetrySync(self.storage, session=NoNetwork())
        sync.last_error = "old error"
        status = sync.clear_local()
        self.assertEqual(status["totals"], dict(person=0, car=0, bicycle=0, motorcycle=0))
        self.assertEqual(status["pending_batches"], 0)
        self.assertEqual(status["recent_sightings"], [])
        self.assertIsNone(status["last_synced_timestamp"])
        self.assertIsNone(status["last_sync_error"])
        self.assertEqual(status["uuid"], identity)
        reopened = DetectionStorage(self.db)
        self.assertEqual(reopened.camera_uuid, identity)
        self.assertEqual(reopened.started_at, self.storage.started_at)
        reopened.seal_due(now=reopened.started_at+3599)
        self.assertIsNone(reopened.pending())
        reopened.record([self.event("car")], now=reopened.started_at+1)
        reopened.seal_due(now=reopened.started_at+3600)
        self.assertEqual(json.loads(reopened.pending()["payload"])["counts"]["car"], 1)

    def test_clear_waits_for_upload_operation(self):
        sync = TelemetrySync(self.storage)
        completed = threading.Event()
        with sync.operation_lock:
            thread = threading.Thread(target=lambda: (sync.clear_local(), completed.set()))
            thread.start()
            self.assertFalse(completed.wait(.1))
        thread.join(3)
        self.assertTrue(completed.is_set())
        sync.stop()

    def test_http_failure_retry_same_payload_and_backlog_order(self):
        bodies = []
        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args): pass
            def do_POST(self):
                body = self.rfile.read(int(self.headers["Content-Length"]))
                bodies.append((self.headers["Idempotency-Key"], body))
                self.send_response(503 if len(bodies) == 1 else 200)
                self.end_headers()

        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
        config = {"server_url": ""}
        sync = TelemetrySync(self.storage, config_loader=lambda: config)
        try:
            self.storage.record([self.event("motorcycle")], now=self.hour-7199)
            self.assertFalse(sync.attempt())  # No endpoint; still seals/preserves data.
            self.assertEqual(self.storage.status()["pending_batches"], 2)
            config["server_url"] = f"http://127.0.0.1:{server.server_port}/stats"
            self.assertFalse(sync.attempt())  # Server unavailable.
            self.assertEqual(self.storage.status()["pending_batches"], 2)
            self.storage.record([self.event("person")], now=self.hour+1)
            self.assertTrue(sync.attempt())
            self.assertEqual(bodies[0], bodies[1])  # Exact same batch ID and bytes on retry.
            self.assertTrue(sync.attempt())
            self.assertFalse(sync.attempt())
            self.assertEqual(self.storage.status()["pending_batches"], 0)
            self.assertEqual(self.storage.status()["counts_since_last_sync"]["person"], 1)
            self.assertNotEqual(bodies[1][0], bodies[2][0])
            self.assertEqual(bodies[0][0], json.loads(bodies[0][1])["batch_id"])
            self.assertEqual(json.loads(bodies[0][1])["counts"]["motorcycle"], 1)
        finally:
            sync.stop(); server.shutdown(); server.server_close(); thread.join()


if __name__ == "__main__":
    unittest.main(verbosity=2)
