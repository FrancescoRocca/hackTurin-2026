"""Train or fine-tune a YOLO11 checkpoint on Apple Metal (no CPU fallback), or resume an interrupted run."""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from runtime import ROOT, image_size, positive_int, probability, require_mps, run_name


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, default=ROOT / "data/coco-traffic/data.yaml")
    parser.add_argument(
        "--model", default=str(ROOT / "models/pretrained/yolo11n.pt"), help="starting weights or checkpoint"
    )
    parser.add_argument("--epochs", type=positive_int, default=50)
    parser.add_argument("--imgsz", type=image_size, default=320)
    parser.add_argument("--batch", type=positive_int, default=16)
    parser.add_argument(
        "--workers", type=int, default=0, help="dataloader workers (0 avoids multiprocessing problems on macOS)"
    )
    parser.add_argument("--name", type=run_name, default="yolo11n-traffic-candidate")
    parser.add_argument("--patience", type=int, default=12)
    parser.add_argument("--mosaic", type=probability, default=1.0, help="mosaic augmentation probability")
    parser.add_argument("--optimizer", choices=["auto", "AdamW", "SGD"], default="auto")
    parser.add_argument("--lr0", type=float, help="initial learning rate (needs --optimizer AdamW or SGD)")
    parser.add_argument("--resume", type=Path, help="resume from a run's weights/last.pt")
    args = parser.parse_args()
    if args.lr0 is not None and (args.lr0 <= 0 or args.optimizer == "auto"):
        parser.error("--lr0 must be positive and needs --optimizer AdamW or SGD (auto ignores it)")
    if args.resume and not args.resume.is_file():
        parser.error(f"checkpoint not found: {args.resume}")
    if not args.resume and not args.data.is_file():
        parser.error("dataset not found: run scripts/download_coco.py first")
    device = require_mps()

    import torch
    import ultralytics
    from ultralytics import YOLO

    model = YOLO(str(args.resume) if args.resume else args.model)
    if args.resume:
        model.train(resume=True, device=device, workers=args.workers, amp=False)
    else:
        optimizer = {"optimizer": args.optimizer}
        if args.lr0 is not None:
            optimizer["lr0"] = args.lr0
            # The default bias warmup learning rate (0.1) would undo a gentle fine-tune.
            optimizer["warmup_bias_lr"] = 0.0
        model.train(
            data=str(args.data.resolve()),
            device=device,
            epochs=args.epochs,
            imgsz=args.imgsz,
            batch=args.batch,
            workers=args.workers,
            project=str(ROOT / "reports/training"),
            name=args.name,
            exist_ok=False,
            patience=args.patience,
            seed=42,
            deterministic=True,
            amp=False,
            cache=False,
            mosaic=args.mosaic,
            close_mosaic=min(10, args.epochs),
            plots=True,
            **optimizer,
        )
    save_dir = Path(model.trainer.save_dir)
    environment = {
        "device": device,
        "torch": torch.__version__,
        "ultralytics": ultralytics.__version__,
        "dataset": str(model.trainer.args.data),
    }
    (save_dir / "environment.json").write_text(json.dumps(environment, indent=2) + "\n")
    print(f"Best weights: {save_dir / 'weights/best.pt'}")


if __name__ == "__main__":
    main()
