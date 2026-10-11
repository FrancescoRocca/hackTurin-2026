# Detection statistics

The Arduino `arduino:dbstorage_sqlstore` brick stores metadata, confirmed
sightings and the HTTP upload queue in `/app/data/detections.db`, which is
`/home/arduino/ArduinoApps/larp_crosswalk/data/detections.db` on the board.
This app directory is mounted persistently: app/container restarts preserve
the data. The `data/` directory is ignored by Git. Do not remove it when
deploying updates. No images or video are stored.

## What is counted

Counts cover `person`, `car`, `bicycle`, and `motorcycle`. `bike` and
`motorbike` labels map to bicycle and motorcycle. Other labels are ignored.
The model's existing confidence filter still applies.

A lightweight tracker matches boxes by class, overlap and predicted position.
An object is counted once after appearing in two processed frames. Further
detections of the same active track do not add to the count. A disappearance
of up to three seconds retains its track; reappearance after that is a new
passage. Camera interruptions, app restarts, overlapping objects and large
movements between inference frames can produce new identities. Objects seen
in only one inference frame are not counted. These are estimates of passages,
not guaranteed identities or distinct people over a whole day. Track identities
are held in RAM; committed sightings, totals and upload identities persist.

Counting happens once per accepted inference result, independently of preview
polling, the ring/LCD loop and HTTP delivery. Each confirmed sighting has a
unique event ID, UTC recording time, class and model confidence. Duplicate
event IDs are ignored by the database. Failed local writes stop the vision
worker rather than silently reporting unrecorded counts.

## Configuration

Edit `telemetry.json` on the board:

```json
{
  "camera_name": "larp_crosswalk",
  "server_url": "https://your-server.example/api/detections"
}
```

Leave `server_url` empty until the endpoint is available. Logging and hourly
batch creation still run. The worker reloads the URL at least every 30 seconds;
no restart is needed to set/change it. `TELEMETRY_URL` overrides the URL, and
`TELEMETRY_CONFIG` can point to another configuration file. If authentication
is needed, `TELEMETRY_TOKEN` adds `Authorization: Bearer <token>`.

The camera ID is `larp_crosswalk_<UUIDv4>`. The UUID and camera name are saved
in the database on first initialization and retained across restarts. Later
configuration changes do not rename an existing identity. Each device needs
its own database; copying another camera's database also copies its identity.

## HTTP contract and offline behavior

Windows are aligned to whole UTC hours, including zero-count windows. The
worker sends closed windows within 30 seconds of each boundary, oldest first.
The active hour remains local until it closes. The first window starts at
the beginning of the UTC hour when the database was created.

HTTP POST sends `Content-Type: application/json` and
`Idempotency-Key: <batch_id>`, with this body:

```json
{
  "uuid": "larp_crosswalk_6ee0daa7-f018-4eec-b9bc-f94cefd211f7",
  "batch_id": "ef07d397-f76f-459e-a398-01ba13504f5a",
  "since": "2026-10-11T09:00:00Z",
  "timestamp": "2026-10-11T10:00:00Z",
  "counts": {"person": 12, "car": 4, "bicycle": 2, "motorcycle": 1},
  "counting_mode": "tracked_objects"
}
```

`since` is inclusive and `timestamp` is exclusive; they describe the count
window, not the actual HTTP send time. After the first batch, `since` matches
the preceding batch's `timestamp`. Offline hours are queued separately and
sent in order as soon as delivery succeeds again. Sightings continue to be
written while HTTP is blocked or unavailable. Network attempts use a 3-second
connection timeout and a 10-second response timeout; unsuccessful delivery is
retried after 30 seconds. Queued data has no automatic expiry.

Only a 2xx response acknowledges a batch. Errors, redirects, timeouts and
connection failures leave it queued. Retries reuse the exact same body and
batch ID, even after restart. If the server accepted a request but its response
was lost, the camera retries it: the server **must deduplicate by batch_id**.
The server should atomically persist the batch and return 2xx only after it is
durable; an already-stored identical batch should also return 2xx without
adding its counts again. Delivery is at least once, not exactly once.

Acknowledged batches and sightings remain in the local database for history.
SQLite uses WAL and FULL synchronous commits. This does not replace backups
or provide unlimited storage: monitor the board's available disk space.

## Inspect and verify

`GET /api/stats` returns the persistent camera ID, lifetime totals, counts
since the last acknowledged window, pending closed batches, last acknowledged
timestamp, whether a server URL is configured, and the last sync error.

Run the checks inside the app container:

```sh
docker exec larp_crosswalk-main-1 python /app/tests/test_telemetry.py
```

Tests use the installed Arduino SQLStore brick, temporary databases (deleted
afterward) and a loopback HTTP server. They cover tracking, hour boundaries,
restart persistence, duplicate events, immutable queued payloads, offline
delivery and exact retry identity. They never upload real camera data.

## Clear board history

The statistics panel includes **Clear board database**, with confirmation. It permanently removes all local sightings, hourly batches (including unsent ones), and sync history, compacts SQLite, and starts a new counting window at deletion time. The stable camera ID and configuration are retained. New sightings continue logging; currently tracked objects are not counted again solely because history was cleared. It never sends a deletion request to the server. An upload already in progress may finish before the reset; previously uploaded server data is unaffected.

The endpoint is `POST /api/stats/clear-local` with header `X-Confirm-Local-Reset: delete-board-data`; cross-site browser requests are rejected. As with the preview, access is intended for the trusted local network.
