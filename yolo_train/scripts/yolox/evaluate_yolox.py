"""Evaluate an exported YOLOX ONNX model with COCO metrics (CPU only, no YOLOX install needed).

uv run --with pycocotools python scripts/yolox/evaluate_yolox.py --model path/to/traffic.onnx
"""

import argparse
import hashlib
import json
import sys
import tempfile
import time
from pathlib import Path

import cv2
import numpy as np
import onnxruntime as ort

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from prepare_yolox import convert_dataset
from preprocessing import letterbox
from runtime import CLASSES, ROOT, positive_int, probability

STRIDES = (8, 16, 32)


def decode(raw, height, width):
    """Turn raw YOLOX box offsets into centre/size boxes in input pixels."""
    grids, strides = [], []
    for stride in STRIDES:
        y, x = np.meshgrid(np.arange(height // stride), np.arange(width // stride), indexing="ij")
        grid = np.stack((x, y), axis=-1).reshape(-1, 2)
        grids.append(grid)
        strides.append(np.full((len(grid), 1), stride))
    grid, stride = np.concatenate(grids), np.concatenate(strides)
    result = raw.copy()
    result[:, :2] = (result[:, :2] + grid) * stride
    result[:, 2:4] = np.exp(result[:, 2:4]) * stride
    return result


def detections(prediction, ratio, score_floor, iou_threshold):
    """Score, threshold and run per-class NMS. Returns (xyxy box, score, class) tuples in image pixels."""
    classes = prediction[:, 5:].argmax(axis=1)
    scores = prediction[:, 4] * prediction[np.arange(len(prediction)), classes + 5]
    mask = scores >= score_floor
    boxes, scores, classes = prediction[mask, :4], scores[mask], classes[mask]
    boxes = np.column_stack((boxes[:, :2] - boxes[:, 2:] / 2, boxes[:, :2] + boxes[:, 2:] / 2)) / ratio
    area = np.maximum(boxes[:, 2:] - boxes[:, :2], 0).prod(axis=1)

    kept = []
    for category in range(len(CLASSES)):
        order = np.where(classes == category)[0]
        order = order[np.argsort(-scores[order])]
        while len(order):
            best, rest = order[0], order[1:]
            kept.append(int(best))
            low = np.maximum(boxes[best, :2], boxes[rest, :2])
            high = np.minimum(boxes[best, 2:], boxes[rest, 2:])
            intersection = np.maximum(high - low, 0).prod(axis=1)
            iou = intersection / np.maximum(area[best] + area[rest] - intersection, 1e-12)
            order = rest[iou <= iou_threshold]
    kept.sort(key=lambda index: -scores[index])
    return [(boxes[i], float(scores[i]), int(classes[i])) for i in kept[:300]]


def load_contract(model_path, parser):
    contract = json.loads(model_path.with_name("model.json").read_text())
    valid = (
        contract.get("architecture") == "YOLOX-Nano"
        and contract.get("classes") == CLASSES
        and contract.get("color") == "BGR"
        and contract.get("range") == [0, 255]
        and isinstance(contract.get("box_decoding_in_graph"), bool)
    )
    if not valid:
        parser.error("expected a four-class YOLOX export with its model.json next to the ONNX file")
    return contract


def per_class_ap(metrics):
    result = {}
    for index, name in enumerate(CLASSES):
        precision = metrics.eval["precision"][:, :, index, 0, -1]
        ap50 = precision[0]
        result[name] = {
            "mAP50_95": float(precision[precision >= 0].mean()) if (precision >= 0).any() else None,
            "mAP50": float(ap50[ap50 >= 0].mean()) if (ap50 >= 0).any() else None,
        }
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--model", type=Path, required=True)
    parser.add_argument("--source", type=Path, default=ROOT / "data/coco-traffic")
    parser.add_argument("--split", choices=["val", "test"], default="test")
    parser.add_argument("--output", type=Path, default=ROOT / "reports/evaluation/yolox-onnx-test")
    parser.add_argument("--limit", type=positive_int, help="only evaluate the first N images")
    parser.add_argument(
        "--score-floor",
        type=probability,
        default=0.001,
        help="lowest score kept (low on purpose: AP needs the full sweep)",
    )
    parser.add_argument("--iou", type=probability, default=0.45, help="per-class NMS threshold")
    args = parser.parse_args()
    if args.output.exists():
        parser.error("the report folder already exists: choose another --output")
    if not 0 < args.score_floor < 1:
        parser.error("--score-floor must be between 0 and 1 (exclusive)")
    contract = load_contract(args.model, parser)
    try:
        from pycocotools.coco import COCO
        from pycocotools.cocoeval import COCOeval
    except ImportError:
        parser.error("pycocotools is missing: run with `uv run --with pycocotools python ...`")

    options = ort.SessionOptions()
    options.intra_op_num_threads = 4
    session = ort.InferenceSession(str(args.model), sess_options=options, providers=["CPUExecutionProvider"])
    input_name = session.get_inputs()[0].name
    shape = session.get_inputs()[0].shape
    if shape != contract["input_shape"] or shape[:2] != [1, 3]:
        parser.error("the ONNX input does not match model.json")
    height, width = shape[2:]
    anchors = sum((height // stride) * (width // stride) for stride in STRIDES)
    if session.get_outputs()[0].shape != [1, anchors, 9]:
        parser.error("unexpected ONNX output shape")

    results, inference_ms = [], []
    with tempfile.TemporaryDirectory(prefix="yolox-eval-") as temporary:
        converted = convert_dataset(args.source, Path(temporary) / "coco")
        ground_truth = COCO(str(converted / "annotations" / f"instances_{args.split}2017.json"))
        ids = sorted(ground_truth.getImgIds())[: args.limit]
        for index, image_id in enumerate(ids, 1):
            path = args.source / "images" / args.split / ground_truth.loadImgs(image_id)[0]["file_name"]
            image = cv2.imread(str(path))
            if image is None:
                raise ValueError(f"Cannot read {path}")
            padded, ratio = letterbox(image, height, width)
            tensor = np.ascontiguousarray(padded.transpose(2, 0, 1)[None], dtype=np.float32)

            started = time.perf_counter()
            raw = session.run(None, {input_name: tensor})[0][0]
            inference_ms.append((time.perf_counter() - started) * 1000)

            if not contract["box_decoding_in_graph"]:
                raw = decode(raw, height, width)
            if not np.isfinite(raw).all():
                raise ValueError(f"Non-finite predictions for {path}")
            for box, score, class_id in detections(raw, ratio, args.score_floor, args.iou):
                x1, y1, x2, y2 = map(float, box)
                results.append(
                    {
                        "image_id": image_id,
                        "category_id": class_id + 1,
                        "bbox": [x1, y1, x2 - x1, y2 - y1],
                        "score": score,
                    }
                )
            if index % 100 == 0 or index == len(ids):
                print(f"Evaluated {index}/{len(ids)} images", flush=True)

        if results:
            predicted = ground_truth.loadRes(results)
        else:
            predicted = COCO()
            predicted.dataset = {
                "images": ground_truth.dataset["images"],
                "categories": ground_truth.dataset["categories"],
                "annotations": [],
            }
            predicted.createIndex()
        metrics = COCOeval(ground_truth, predicted, "bbox")
        metrics.params.imgIds = ids
        metrics.evaluate()
        metrics.accumulate()
        metrics.summarize()
        per_class = per_class_ap(metrics)
        report = {
            "model": str(args.model.resolve()),
            "model_sha256": hashlib.sha256(args.model.read_bytes()).hexdigest(),
            "dataset": str(args.source.resolve()),
            "split": args.split,
            "images": len(ids),
            "partial_evaluation": len(ids) != len(ground_truth.getImgIds()),
            "mAP50": float(metrics.stats[1]),
            "mAP50_95": float(metrics.stats[0]),
            "average_recall_at_100": float(metrics.stats[8]),
            "per_class": per_class,
            "nms_iou": args.iou,
            "score_floor": args.score_floor,
            "cpu_inference_mean_ms": float(np.mean(inference_ms)),
            "note": "COCO metrics on the prepared subset. CPU timing from this machine, not from the UNO Q.",
        }

    args.output.mkdir(parents=True)
    (args.output / "summary.json").write_text(json.dumps(report, indent=2) + "\n")
    (args.output / "predictions.json").write_text(json.dumps(results) + "\n")
    print(f"Report: {args.output / 'summary.json'}")
    for name, values in per_class.items():
        print(f"{name}: {values}")


if __name__ == "__main__":
    main()
