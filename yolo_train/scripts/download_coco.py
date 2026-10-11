"""Build the four-class COCO 2017 traffic subset (car, bicycle, motorcycle, pedestrian) in YOLO format."""

import argparse
import hashlib
import json
import random
import time
import urllib.request
import zipfile
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import yaml
from PIL import Image

from runtime import CLASSES, ROOT, positive_int, probability

LABELS_URL = "https://github.com/ultralytics/assets/releases/download/v0.0.0/coco2017labels.zip"
IMAGE_BASE = "https://s3.amazonaws.com/images.cocodataset.org"

# Ultralytics COCO class id -> index in CLASSES (0 person, 1 bicycle, 2 car, 3 motorcycle).
REMAP = {2: 0, 1: 1, 3: 2, 0: 3}


def download(url, target):
    """Download a zip archive unless a valid copy is already on disk."""
    if target.exists() and zipfile.is_zipfile(target):
        print(f"Using cached {target.name}", flush=True)
        return
    partial = target.with_suffix(".zip.part")
    for attempt in range(3):
        try:
            request = urllib.request.Request(url, headers={"User-Agent": "uno-q-coco/1.0"})
            with urllib.request.urlopen(request, timeout=90) as response, partial.open("wb") as out:
                total = int(response.headers.get("Content-Length", 0))
                done = last = 0
                while chunk := response.read(1024 * 1024):
                    out.write(chunk)
                    done += len(chunk)
                    if done - last >= 32 * 1024 * 1024:
                        print(f"{target.name}: {done / 1e6:.0f} / {total / 1e6:.0f} MB", flush=True)
                        last = done
            if not zipfile.is_zipfile(partial):
                raise ValueError(f"Not a zip archive: {url}")
            partial.replace(target)
            return
        except Exception:
            if attempt == 2:
                raise
            time.sleep(2**attempt)


def read_labels(archive):
    """Return {source split: {image id: [[class, cx, cy, w, h], ...]}} for the target classes."""
    pools = {"train2017": {}, "val2017": {}}
    with zipfile.ZipFile(archive) as z:
        for info in z.infolist():
            path = Path(info.filename)
            if path.suffix != ".txt" or "labels" not in path.parts:
                continue
            source = next((s for s in pools if s in path.parts), None)
            if source is None:
                continue
            labels = []
            for line in z.read(info).decode().splitlines():
                parts = line.split()
                if not parts or int(parts[0]) not in REMAP:
                    continue
                if len(parts) != 5:
                    raise ValueError(f"Expected bounding boxes, found a segment: {info.filename}")
                box = [float(v) for v in parts[1:]]
                if not all(0 <= v <= 1 for v in box) or min(box[2:]) <= 0:
                    raise ValueError(f"Invalid box in {info.filename}")
                labels.append([REMAP[int(parts[0])], *box])
            pools[source][path.stem] = labels
    if not all(pools.values()):
        raise ValueError("The label archive has no train2017 or val2017 detection labels")
    return pools


def sample_images(ids, labels, per_class, negative_ratio, rng):
    """Pick `per_class` images for every class, then add background images."""
    selected = set()
    for class_id, name in enumerate(CLASSES):
        candidates = sorted(i for i in ids if any(row[0] == class_id for row in labels[i]))
        if not candidates:
            raise ValueError(f"No {name} examples in this split")
        selected.update(rng.sample(candidates, min(per_class, len(candidates))))
    backgrounds = sorted(i for i in ids if not labels[i])
    selected.update(rng.sample(backgrounds, min(len(backgrounds), round(len(selected) * negative_ratio))))
    return sorted(selected)


def fetch_image(source, image_id, destination):
    if destination.exists():
        with Image.open(destination) as image:
            image.verify()
        return
    url = f"{IMAGE_BASE}/{source}/{image_id}.jpg"
    partial = destination.with_suffix(".jpg.part")
    for attempt in range(4):
        try:
            request = urllib.request.Request(url, headers={"User-Agent": "uno-q-coco/1.0"})
            with urllib.request.urlopen(request, timeout=60) as response, partial.open("wb") as out:
                while chunk := response.read(1024 * 1024):
                    out.write(chunk)
            with Image.open(partial) as image:
                image.verify()
            partial.replace(destination)
            return
        except Exception as error:
            if attempt == 3:
                raise RuntimeError(f"Image download failed: {url}") from error
            time.sleep(2**attempt)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "data/coco-traffic")
    parser.add_argument(
        "--per-class",
        type=positive_int,
        default=1500,
        help="training images sampled per class (images with several classes can push the total higher)",
    )
    parser.add_argument("--test-per-class", type=positive_int, default=500)
    parser.add_argument("--negative-ratio", type=probability, default=0.15, help="background images per positive image")
    parser.add_argument("--val-fraction", type=float, default=0.1)
    parser.add_argument("--workers", type=positive_int, default=32, help="parallel image downloads")
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()
    if not 0 < args.val_fraction < 1:
        parser.error("--val-fraction must be between 0 and 1")

    output = args.output.resolve()
    settings = {k: getattr(args, k) for k in ("per_class", "test_per_class", "negative_ratio", "val_fraction", "seed")}
    manifest_path = output / "manifest.json"
    if manifest_path.exists():
        existing = json.loads(manifest_path.read_text())
        if existing.get("settings") != settings or existing.get("classes") != CLASSES:
            parser.error("Dataset settings differ from the existing one; choose another --output")
        if (output / "data.yaml").exists():
            print(f"Dataset ready: {output / 'data.yaml'}")
            return
    elif (output / "data.yaml").exists():
        parser.error("data.yaml exists without a manifest; choose another --output")

    output.mkdir(parents=True, exist_ok=True)
    # Written first so an interrupted download cannot be resumed with different settings.
    manifest_path.write_text(
        json.dumps({"status": "preparing", "settings": settings, "classes": CLASSES}, indent=2) + "\n"
    )
    archive = output / "source-labels.zip"
    download(LABELS_URL, archive)
    pools = read_labels(archive)
    rng = random.Random(args.seed)

    # Split by image before sampling per class, so images with several classes cannot leak across splits.
    train_pool = pools["train2017"]
    train_ids, val_ids = [], []
    for has_objects in (True, False):
        group = sorted(i for i, boxes in train_pool.items() if bool(boxes) == has_objects)
        rng.shuffle(group)
        cutoff = round(len(group) * args.val_fraction)
        val_ids.extend(group[:cutoff])
        train_ids.extend(group[cutoff:])
    val_per_class = max(1, round(args.per_class * args.val_fraction))
    splits = {
        "train": ("train2017", sample_images(train_ids, train_pool, args.per_class, args.negative_ratio, rng)),
        "val": ("train2017", sample_images(val_ids, train_pool, val_per_class, args.negative_ratio, rng)),
        "test": (
            "val2017",
            sample_images(list(pools["val2017"]), pools["val2017"], args.test_per_class, args.negative_ratio, rng),
        ),
    }
    image_sets = [set(ids) for _, ids in splits.values()]
    if any(a & b for i, a in enumerate(image_sets) for b in image_sets[i + 1 :]):
        raise ValueError("Image ids overlap between splits")

    report = {
        "source": "COCO 2017, Ultralytics detection labels",
        "labels_url": LABELS_URL,
        "image_base": IMAGE_BASE,
        "settings": settings,
        "classes": CLASSES,
        "source_to_target_class_ids": REMAP,
        "notes": [
            "Every target box on a selected image is kept, including classes that were not sampled for it.",
            "Sampling balances image counts, not box counts.",
            "The upstream label conversion drops crowd annotations.",
            "Validation images come from COCO train2017, which the pretrained weights have already seen.",
            "Test images come from COCO val2017, which upstream also uses to evaluate pretrained weights.",
        ],
        "splits": {},
    }
    downloads = []
    for split, (source, ids) in splits.items():
        image_dir = output / "images" / split
        label_dir = output / "labels" / split
        image_dir.mkdir(parents=True, exist_ok=True)
        label_dir.mkdir(parents=True, exist_ok=True)
        counts = Counter()
        backgrounds = 0
        for image_id in ids:
            boxes = pools[source][image_id]
            backgrounds += not boxes
            lines = []
            for class_id, *box in boxes:
                counts[CLASSES[class_id]] += 1
                lines.append(f"{class_id} " + " ".join(f"{v:.8f}" for v in box))
            (label_dir / f"{image_id}.txt").write_text("\n".join(lines) + ("\n" if lines else ""))
            downloads.append((source, image_id, image_dir / f"{image_id}.jpg"))
        report["splits"][split] = {
            "source_split": source,
            "images": len(ids),
            "backgrounds": backgrounds,
            "instances": dict(counts),
            "image_ids": ids,
        }
        print(f"{split}: {len(ids)} images, instances: {dict(counts)}", flush=True)

    pool = ThreadPoolExecutor(max_workers=args.workers)
    pending = [pool.submit(fetch_image, *task) for task in downloads]
    try:
        for done, future in enumerate(as_completed(pending), 1):
            future.result()
            if done % 100 == 0 or done == len(downloads):
                print(f"Images ready: {done}/{len(downloads)}", flush=True)
    finally:
        pool.shutdown(wait=True, cancel_futures=True)

    with archive.open("rb") as source:
        report["labels_sha256"] = hashlib.file_digest(source, "sha256").hexdigest()
    report["status"] = "ready"
    manifest_path.write_text(json.dumps(report, indent=2) + "\n")
    config = {
        "path": str(output),
        "train": "images/train",
        "val": "images/val",
        "test": "images/test",
        "names": dict(enumerate(CLASSES)),
    }
    (output / "data.yaml").write_text(yaml.safe_dump(config, sort_keys=False))
    print(f"Dataset ready: {output / 'data.yaml'}")


if __name__ == "__main__":
    main()
