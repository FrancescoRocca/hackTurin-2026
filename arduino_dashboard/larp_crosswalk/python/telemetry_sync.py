"""Hourly batches, independent HTTP delivery, and configuration reloading."""
import json
import os
from pathlib import Path
import threading
from urllib.parse import urlparse

import requests


CONFIG_PATH = Path(os.getenv("TELEMETRY_CONFIG", str(Path(__file__).resolve().parents[1] / "telemetry.json")))


def load_config():
    config = json.loads(CONFIG_PATH.read_text()) if CONFIG_PATH.exists() else {}
    url = os.getenv("TELEMETRY_URL", config.get("server_url", "")).strip()
    if url and (urlparse(url).scheme not in ("http", "https") or not urlparse(url).hostname):
        raise ValueError("server_url must be a complete HTTP or HTTPS URL")
    return {"camera_name": config.get("camera_name", "larp_crosswalk"), "server_url": url}


class TelemetrySync:
    def __init__(self, storage, config_loader=load_config, session=None):
        self.storage = storage
        self.config_loader = config_loader
        self.session = session or requests.Session()
        self.stopping = threading.Event()
        self.thread = None
        self.last_error = None
        self.configured = False
        self.operation_lock = threading.Lock()

    def clear_local(self):
        # Wait for an already-started upload before clearing its local batch.
        # This action itself never contacts the server.
        with self.operation_lock:
            self.storage.clear_local()
            self.last_error = None
            return self.status()

    def attempt(self):
        with self.operation_lock:
            return self._attempt()

    def _attempt(self):
        """Return True if a batch was accepted; never hold a DB lock over HTTP."""
        self.storage.seal_due()
        try:
            config = self.config_loader()
            self.configured = bool(config["server_url"])
            if not self.configured:
                self.last_error = None
                return False
            batch = self.storage.pending()
            if batch is None:
                self.last_error = None
                return False
            headers = {"Content-Type": "application/json", "Idempotency-Key": batch["batch_id"]}
            token = os.getenv("TELEMETRY_TOKEN")
            if token:
                headers["Authorization"] = f"Bearer {token}"
            response = self.session.post(config["server_url"], data=batch["payload"].encode(),
                                         headers=headers, timeout=(3, 10), allow_redirects=False)
            try:
                if not 200 <= response.status_code < 300:
                    raise RuntimeError(f"Telemetry server returned HTTP {response.status_code}")
            finally:
                response.close()
            self.storage.acknowledge(batch["batch_id"])
            self.last_error = None
            print(f'Telemetry: delivered batch {batch["batch_id"]}', flush=True)
            return True
        except Exception as exc:
            error = str(exc)
            if error != self.last_error:
                print(f"Telemetry: retaining local data; {error}", flush=True)
            self.last_error = error
            return False

    def _run(self):
        while not self.stopping.is_set():
            try:
                delivered = self.attempt()
            except Exception as exc:
                self.last_error = str(exc)
                print(f"Telemetry database error: {exc}", flush=True)
                delivered = False
            # Drain backlog immediately; retry network failures within 30 seconds.
            self.stopping.wait(0.1 if delivered else 30)

    def start(self):
        if self.thread is None:
            self.thread = threading.Thread(target=self._run, name="TelemetrySync", daemon=True)
            self.thread.start()

    def stop(self):
        self.stopping.set()
        if self.thread is not None:
            self.thread.join(timeout=15)
        self.session.close()

    def status(self):
        return {**self.storage.status(), "server_configured": self.configured, "last_sync_error": self.last_error}
