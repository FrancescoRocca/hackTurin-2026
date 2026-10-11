"""Train YOLO11n on Apple Metal, then export the best checkpoint to ONNX for Edge Impulse."""

import argparse
import json
import subprocess
import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from runtime import CLASSES, ROOT, class_list, image_size, positive_int, require_mps, run_name


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prepare-data", action="store_true", help="download and build the COCO subset first")
    parser.add_argument("--data", type=Path, default=ROOT / "data/coco-traffic/data.yaml")
    parser.add_argument("--epochs", type=positive_int, default=50)
    parser.add_argument("--imgsz", type=image_size, default=320)
    parser.add_argument("--batch", type=positive_int, default=16)
    parser.add_argument("--name", type=run_name, default="yolo11n-traffic")
    parser.add_argument("--patience", type=int, default=0, help="early stopping patience (0 trains for all epochs)")
    parser.add_argument(
        "--per-class", type=positive_int, default=1500, help="training images per class (with --prepare-data)"
    )
    parser.add_argument(
        "--test-per-class", type=positive_int, default=500, help="test images per class (with --prepare-data)"
    )
    parser.add_argument("--download-workers", type=positive_int, default=32)
    args = parser.parse_args()
    if args.patience < 0:
        parser.error("--patience cannot be negative")

    data = args.data.resolve()
    run_dir = ROOT / "reports/training" / args.name
    export_dir = ROOT / "models/edge-impulse" / args.name
    if run_dir.exists() or export_dir.exists():
        parser.error("the run or export folder already exists: pick a new --name")
    device = require_mps()  # fail now, before downloading anything

    if args.prepare_data:
        if data.name != "data.yaml":
            parser.error("--prepare-data needs --data to point to a data.yaml file")
        # fmt: off
        download = [sys.executable, ROOT / "scripts/download_coco.py", "--output", data.parent,
                    "--per-class", args.per_class, "--test-per-class", args.test_per_class,
                    "--workers", args.download_workers]
        # fmt: on
        subprocess.run(list(map(str, download)), check=True, cwd=ROOT)
    if not data.is_file():
        parser.error("dataset not found: use --prepare-data or pass a four-class --data file")
    names = class_list(yaml.safe_load(data.read_text()).get("names"))
    if names != CLASSES:
        parser.error(f"dataset classes must be exactly {CLASSES}, got {names}")

    import torch
    import ultralytics
    from ultralytics import YOLO

    initial_weights = ROOT / "models/pretrained/yolo11n.pt"
    initial_weights.parent.mkdir(parents=True, exist_ok=True)
    print(f"Training YOLO11n on {CLASSES}: {args.epochs} epochs, {args.imgsz}px, batch {args.batch}", flush=True)
    model = YOLO(str(initial_weights), task="detect")  # downloads the official weights if missing

    run_dir.mkdir(parents=True)
    record_path = run_dir / "pipeline.json"
    record = {
        "status": "training",
        "architecture": "YOLO11n",
        "classes": CLASSES,
        "dataset": str(data),
        "initial_weights": str(initial_weights),
        "epochs_requested": args.epochs,
        "imgsz": args.imgsz,
        "batch": args.batch,
        "device": device,
        "patience": args.patience,
        "seed": 42,
        "optimizer": "auto",
        "mosaic": 1.0,
        "close_mosaic": min(10, args.epochs),
        "torch": torch.__version__,
        "ultralytics": ultralytics.__version__,
        "export": {"format": "onnx", "precision": "FP32", "opset": 13, "batch": 1, "dynamic": False, "nms": False},
    }

    def save_record():
        record_path.write_text(json.dumps(record, indent=2) + "\n")

    save_record()
    try:
        model.train(
            data=str(data),
            device=device,
            epochs=args.epochs,
            imgsz=args.imgsz,
            batch=args.batch,
            workers=0,
            project=str(run_dir.parent),
            name=args.name,
            exist_ok=True,  # the folder was just created above; this stops Ultralytics adding a suffix
            patience=args.patience,
            seed=42,
            deterministic=True,
            optimizer="auto",
            amp=False,
            cache=False,
            mosaic=1.0,
            close_mosaic=min(10, args.epochs),
            plots=True,
        )
        best = Path(model.trainer.save_dir) / "weights/best.pt"
        if not best.is_file():
            raise RuntimeError(f"best checkpoint missing: {best}")
        trained = YOLO(str(best)).names
        if [trained[i] for i in range(len(trained))] != CLASSES:
            raise RuntimeError("the trained checkpoint has a different class order")

        record.update(status="exporting", best_weights=str(best))
        save_record()
        # fmt: off
        export = [sys.executable, ROOT / "scripts/yolo11/export_yolo11.py", "--weights", best,
                  "--output", export_dir, "--filename", "traffic.onnx", "--imgsz", args.imgsz]
        # fmt: on
        subprocess.run(list(map(str, export)), check=True, cwd=ROOT)
        record.update(status="complete", onnx=str(export_dir / "traffic.onnx"))
        save_record()
        print(f"\nBest checkpoint: {best}\nONNX: {export_dir / 'traffic.onnx'}")
        print("Edge Impulse: Image / RGB 0..1 / Object detection / YOLOv11 (absolute coordinates)")
        print(f"Labels, in this order: {','.join(CLASSES)}")
    except BaseException as error:
        interrupted = isinstance(error, KeyboardInterrupt)
        record.update(
            status="interrupted" if interrupted else "failed",
            failed_stage=record["status"],
            error=f"{type(error).__name__}: {error}",
        )
        save_record()
        raise


if __name__ == "__main__":
    main()
