"""Evaluate YOLO11 weights on the test split (or the validation split) and write a JSON summary."""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from runtime import ROOT, image_size, positive_int, probability, require_mps


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--weights", type=Path, default=ROOT / "reports/training/yolo11n-traffic/weights/best.pt")
    parser.add_argument("--data", type=Path, default=ROOT / "data/coco-traffic/data.yaml")
    parser.add_argument("--split", choices=["val", "test"], default="test")
    parser.add_argument("--imgsz", type=image_size, default=320)
    parser.add_argument("--batch", type=positive_int, default=16)
    parser.add_argument("--name", help="report folder name (a numeric suffix is added if it exists)")
    parser.add_argument(
        "--confusion-conf",
        type=probability,
        default=0.25,
        help="confidence threshold for the confusion matrix only; AP always uses every score",
    )
    args = parser.parse_args()
    if not args.weights.is_file() or not args.data.is_file():
        parser.error("weights or dataset not found: prepare the dataset and train first")
    device = require_mps()

    from ultralytics import YOLO
    from ultralytics.models.yolo.detect import DetectionValidator

    class FixedConfidenceValidator(DetectionValidator):
        """Build the confusion matrix at a fixed confidence instead of Ultralytics' near-zero default."""

        def init_metrics(self, model):
            super().init_metrics(model)
            process_batch = self.confusion_matrix.process_batch

            def at_fixed_confidence(detections, batch, **kwargs):
                return process_batch(detections, batch, conf=args.confusion_conf, iou_thres=0.45)

            self.confusion_matrix.process_batch = at_fixed_confidence

    model = YOLO(str(args.weights))
    metrics = model.val(
        validator=FixedConfidenceValidator,
        data=str(args.data.resolve()),
        split=args.split,
        device=device,
        imgsz=args.imgsz,
        batch=args.batch,
        workers=0,
        plots=True,
        project=str(ROOT / "reports/evaluation"),
        name=args.name or args.split,
    )
    report = {
        "weights": str(args.weights.resolve()),
        "split": args.split,
        "dataset": str(args.data.resolve()),
        "imgsz": args.imgsz,
        "batch": args.batch,
        "device": device,
        "metrics": {k: float(v) for k, v in metrics.results_dict.items()},
        "per_class_mAP50_95": {
            model.names[int(i)]: float(v) for i, v in zip(metrics.box.ap_class_index, metrics.box.ap, strict=True)
        },
        "speed_ms_per_image": metrics.speed,
        "note": "Timing is from this machine, not from the UNO Q.",
    }
    confusion = getattr(metrics, "confusion_matrix", None)
    if confusion is not None:
        report["confusion_matrix"] = {
            "labels": [model.names[i] for i in range(len(model.names))] + ["background"],
            "rows": "predicted",
            "columns": "true",
            "counts": confusion.matrix.tolist(),
            "confidence_threshold": args.confusion_conf,
            "matching_iou": 0.45,
        }
    target = Path(metrics.save_dir) / "summary.json"
    target.write_text(json.dumps(report, indent=2) + "\n")
    print(f"Report: {target}")


if __name__ == "__main__":
    main()
