"""Convert the YOLO-format traffic dataset to the COCO layout that YOLOX expects."""

import argparse
import json
import math
import sys
from pathlib import Path

import yaml
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from runtime import CLASSES, ROOT, class_list

SPLITS = {"train": "train2017", "val": "val2017", "test": "test2017"}


def read_boxes(label, width, height):
    """Yield (class index, x, y, w, h) in pixels for every box of a YOLO label file."""
    for line_number, line in enumerate(label.read_text().splitlines(), 1):
        if not line.strip():
            continue
        fields = line.split()
        if len(fields) != 5:
            raise ValueError(f"Invalid label at {label}:{line_number}")
        class_id = int(fields[0])
        cx, cy, w, h = map(float, fields[1:])
        if (
            class_id not in range(len(CLASSES))
            or not all(math.isfinite(v) and 0 <= v <= 1 for v in (cx, cy, w, h))
            or min(w, h) <= 0
        ):
            raise ValueError(f"Invalid box at {label}:{line_number}")
        x1, y1 = max(0, (cx - w / 2) * width), max(0, (cy - h / 2) * height)
        x2, y2 = min(width, (cx + w / 2) * width), min(height, (cy + h / 2) * height)
        if x2 <= x1 or y2 <= y1:
            raise ValueError(f"Box is empty after clipping at {label}:{line_number}")
        yield class_id, x1, y1, x2 - x1, y2 - y1


def convert_dataset(source, output):
    source, output = Path(source).resolve(), Path(output).resolve()
    config = yaml.safe_load((source / "data.yaml").read_text())
    names = class_list(config.get("names"))
    if names != CLASSES:
        raise ValueError(f"Expected classes {CLASSES}, got {names}")
    if output == source or output in source.parents or source in output.parents:
        raise ValueError("Source and output must be separate, non-nested directories")
    if output.exists():
        raise FileExistsError(f"Output already exists: {output}")

    # Everything is validated before anything is written. An empty label file is a
    # background image; a missing one is an error.
    documents, seen = {}, set()
    for split, target in SPLITS.items():
        if config.get(split) != f"images/{split}":
            raise ValueError(f"Expected images/{split} in data.yaml")
        images = sorted((source / "images" / split).glob("*.jpg"))
        if not images:
            raise ValueError(f"No images in {source / 'images' / split}")
        document = {
            "info": {},
            "licenses": [],
            "images": [],
            "annotations": [],
            "categories": [{"id": i + 1, "name": name} for i, name in enumerate(CLASSES)],
        }
        for image_id, image in enumerate(images, 1):
            if image.stem in seen:
                raise ValueError(f"Image appears in more than one split: {image.stem}")
            seen.add(image.stem)
            with Image.open(image) as opened:
                width, height = opened.size
                opened.verify()
            document["images"].append({"id": image_id, "file_name": image.name, "width": width, "height": height})
            label = source / "labels" / split / f"{image.stem}.txt"
            for class_id, x, y, w, h in read_boxes(label, width, height):
                document["annotations"].append(
                    {
                        "id": len(document["annotations"]) + 1,
                        "image_id": image_id,
                        "category_id": class_id + 1,
                        "bbox": [x, y, w, h],
                        "area": w * h,
                        "iscrowd": 0,
                    }
                )
        documents[target] = document

    (output / "annotations").mkdir(parents=True)
    for split, target in SPLITS.items():
        # Symlink the images instead of copying them; the source dataset has to stay in place.
        (output / target).symlink_to(source / "images" / split, target_is_directory=True)
        path = output / "annotations" / f"instances_{target}.json"
        path.write_text(json.dumps(documents[target]) + "\n")
        print(
            f"{split}: {len(documents[target]['images'])} images, {len(documents[target]['annotations'])} boxes",
            flush=True,
        )
    provenance = {
        "source": str(source),
        "classes": CLASSES,
        "note": "Same splits as the source dataset; images are symlinked.",
    }
    (output / "conversion.json").write_text(json.dumps(provenance, indent=2) + "\n")
    return output


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=ROOT / "data/coco-traffic")
    parser.add_argument("--output", type=Path, default=ROOT / "data/coco-traffic-yolox")
    args = parser.parse_args()
    print(f"YOLOX dataset: {convert_dataset(args.source, args.output)}")


if __name__ == "__main__":
    main()
