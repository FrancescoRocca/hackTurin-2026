"""Lightweight class-aware box tracking for counting observed passages."""
import math
import uuid


CLASSES = ("person", "car", "bicycle", "motorcycle")
ALIASES = {**{name: name for name in CLASSES}, "bike": "bicycle", "motorbike": "motorcycle"}


def overlap(a, b):
    intersection = max(0, min(a[2], b[2]) - max(a[0], b[0])) * max(0, min(a[3], b[3]) - max(a[1], b[1]))
    area = lambda box: (box[2] - box[0]) * (box[3] - box[1])
    return intersection / max(area(a) + area(b) - intersection, 1)


def center(box):
    return ((box[0] + box[2]) / 2, (box[1] + box[3]) / 2)


class ObjectTracker:
    def __init__(self, max_age=3.0, min_hits=2):
        self.max_age = max_age
        self.min_hits = min_hits
        self.tracks = {}
        self.generation = None

    def update(self, detections, timestamp, width, height, generation=0):
        if generation != self.generation:
            self.tracks.clear()
            self.generation = generation
        self.tracks = {key: track for key, track in self.tracks.items()
                       if 0 <= timestamp - track["seen"] <= self.max_age}
        boxes = []
        for item in detections:
            label = ALIASES.get(item.get("class_name", "").strip().casefold())
            try:
                box = tuple(float(v) for v in item["bounding_box_xyxy"])
                confidence = float(item["confidence"])
            except (KeyError, TypeError, ValueError):
                continue
            if label and len(box) == 4 and all(math.isfinite(v) for v in (*box, confidence)) and box[2] > box[0] and box[3] > box[1]:
                boxes.append((label, box, confidence))

        diagonal = max(math.hypot(width, height), 1)
        candidates = []
        for key, track in self.tracks.items():
            dt = timestamp - track["seen"]
            dx, dy = (v * dt for v in track["velocity"])
            previous = track["box"]
            predicted = (previous[0] + dx, previous[1] + dy, previous[2] + dx, previous[3] + dy)
            for index, (label, box, _) in enumerate(boxes):
                if label != track["class"]:
                    continue
                distance = math.dist(center(predicted), center(box)) / diagonal
                iou = overlap(predicted, box)
                if distance <= 0.3 and (iou >= 0.05 or distance <= 0.12):
                    candidates.append((distance + (1 - iou) * 0.3, key, index))
        matches, used_tracks, used_boxes = {}, set(), set()
        for _, key, index in sorted(candidates):
            if key not in used_tracks and index not in used_boxes:
                matches[index] = key
                used_tracks.add(key)
                used_boxes.add(index)

        events = []
        for index, (label, box, confidence) in enumerate(boxes):
            key = matches.get(index)
            if key is None:
                key = str(uuid.uuid4())
                self.tracks[key] = {"class": label, "box": box, "seen": timestamp,
                                    "velocity": (0, 0), "hits": 0, "counted": False}
            track = self.tracks[key]
            dt = timestamp - track["seen"]
            if dt > 0:
                old, new = center(track["box"]), center(box)
                track["velocity"] = tuple((b - a) / dt * 0.5 + v * 0.5
                                          for a, b, v in zip(old, new, track["velocity"]))
            track.update(box=box, seen=timestamp, hits=track["hits"] + 1)
            if not track["counted"] and track["hits"] >= self.min_hits:
                events.append({"event_id": key, "class": label, "confidence": confidence})
                track["counted"] = True
        return events
