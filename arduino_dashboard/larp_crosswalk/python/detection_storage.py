"""Durable sightings and immutable hourly uploads using Arduino SQLStore."""
from datetime import datetime, timezone
import json
import math
import re
import sqlite3
import threading
import time
import uuid

from object_tracker import CLASSES


def utc(timestamp):
    return datetime.fromtimestamp(timestamp, timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


class DetectionStorage:
    def __init__(self, db, camera_name="larp_crosswalk", interval=3600, now=None):
        if not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", camera_name):
            raise ValueError("Camera name must contain 1-64 letters, numbers, underscores or hyphens")
        self.db = db
        self.lock = threading.RLock()
        self.interval = interval
        self.db.execute_sql("PRAGMA journal_mode=WAL")
        self.db.execute_sql("PRAGMA synchronous=FULL")
        self.db.execute_sql("CREATE TABLE IF NOT EXISTS telemetry_meta (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
        self.db.execute_sql("""CREATE TABLE IF NOT EXISTS sightings (
            event_id TEXT PRIMARY KEY, timestamp REAL NOT NULL,
            class TEXT NOT NULL, confidence REAL NOT NULL)""")
        self.db.execute_sql("CREATE INDEX IF NOT EXISTS sightings_time ON sightings(timestamp)")
        self.db.execute_sql("""CREATE TABLE IF NOT EXISTS sync_batches (
            batch_id TEXT PRIMARY KEY, window_start REAL UNIQUE NOT NULL,
            window_end REAL NOT NULL, payload TEXT NOT NULL, acknowledged_at REAL)""")
        now = time.time() if now is None else now
        for key, value in (("internal_id", str(uuid.uuid4())), ("camera_name", camera_name),
                           ("interval", str(interval)), ("started_at", str(math.floor(now / interval) * interval))):
            self.db.execute_sql("INSERT OR IGNORE INTO telemetry_meta VALUES (?, ?)", (key, value))
        metadata = {row["key"]: row["value"] for row in self.db.read("telemetry_meta")}
        self.camera_uuid = f'{metadata["camera_name"]}_{metadata["internal_id"]}'
        self.started_at = float(metadata["started_at"])
        if int(metadata["interval"]) != interval:
            raise ValueError("Changing the sync interval of an existing database is unsupported")

    def record(self, events, now=None):
        if not events:
            return
        with self.lock:
            now = time.time() if now is None else now
            sealed = self.db.execute_sql("SELECT MAX(window_end) AS end FROM sync_batches")[0]["end"]
            # Never insert into an already frozen batch if the wall clock moves back.
            now = max(now, sealed or self.started_at)
            values = []
            for event in events:
                if event["class"] not in CLASSES:
                    raise ValueError("Unsupported sighting class")
                values.extend((event["event_id"], now, event["class"], event["confidence"]))
            placeholders = ",".join("(?,?,?,?)" for _ in events)
            self.db.execute_sql(f"INSERT OR IGNORE INTO sightings VALUES {placeholders}", tuple(values))

    def _counts(self, start=None, end=None):
        condition, args = "", ()
        if start is not None:
            condition, args = "WHERE timestamp >= ? AND timestamp < ?", (start, end)
        rows = self.db.execute_sql(f"SELECT class, COUNT(*) AS n FROM sightings {condition} GROUP BY class", args) or []
        return {name: next((row["n"] for row in rows if row["class"] == name), 0) for name in CLASSES}

    def seal_due(self, now=None):
        with self.lock:
            now = time.time() if now is None else now
            row = self.db.execute_sql("SELECT MAX(window_end) AS end FROM sync_batches")[0]
            start = row["end"] if row["end"] is not None else self.started_at
            while start + self.interval <= now:
                end, batch_id = start + self.interval, str(uuid.uuid4())
                payload = {"uuid": self.camera_uuid, "batch_id": batch_id,
                           "since": utc(start), "timestamp": utc(end),
                           "counts": self._counts(start, end), "counting_mode": "tracked_objects"}
                self.db.execute_sql("INSERT INTO sync_batches VALUES (?,?,?,?,NULL)",
                                    (batch_id, start, end, json.dumps(payload, separators=(",", ":"), sort_keys=True)))
                start = end

    def pending(self):
        with self.lock:
            rows = self.db.execute_sql("SELECT * FROM sync_batches WHERE acknowledged_at IS NULL ORDER BY window_start LIMIT 1")
            return rows[0] if rows else None

    def acknowledge(self, batch_id, now=None):
        with self.lock:
            self.db.execute_sql("UPDATE sync_batches SET acknowledged_at=? WHERE batch_id=? AND acknowledged_at IS NULL",
                                (time.time() if now is None else now, batch_id))

    def clear_local(self, now=None):
        """Clear local history atomically, retaining the stable camera identity."""
        with self.lock:
            started_at = time.time() if now is None else now
            # SQLStore commits each execute_sql call. A separate SQLite transaction
            # makes the multi-table reset atomic without using brick internals.
            with sqlite3.connect(self.db.database_name) as connection:
                connection.execute("PRAGMA secure_delete=ON")
                connection.execute("DELETE FROM sightings")
                connection.execute("DELETE FROM sync_batches")
                connection.execute("UPDATE telemetry_meta SET value=? WHERE key='started_at'",
                                   (str(started_at),))
            self.started_at = started_at
            self.db.execute_sql("PRAGMA wal_checkpoint(TRUNCATE)")
            self.db.execute_sql("VACUUM")
            self.db.execute_sql("PRAGMA wal_checkpoint(TRUNCATE)")

    def status(self):
        with self.lock:
            row = self.db.execute_sql("""SELECT COUNT(*) AS pending_batches,
                MIN(window_start) AS oldest FROM sync_batches WHERE acknowledged_at IS NULL""")[0]
            last = self.db.execute_sql("SELECT MAX(window_end) AS end FROM sync_batches WHERE acknowledged_at IS NOT NULL")[0]["end"]
            recent = self.db.execute_sql("SELECT timestamp, class, confidence FROM sightings ORDER BY timestamp DESC LIMIT 5") or []
            return {"uuid": self.camera_uuid, "counting_mode": "tracked_objects",
                    "totals": self._counts(), "pending_batches": row["pending_batches"],
                    "last_synced_timestamp": utc(last) if last is not None else None,
                    "recent_sightings": [{**item, "timestamp": utc(item["timestamp"])} for item in recent],
                    "counts_since_last_sync": self._counts(last if last is not None else self.started_at, float("inf"))}
