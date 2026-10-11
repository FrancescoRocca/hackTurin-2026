"""Train YOLOX-Nano on a single NVIDIA GPU with the traffic dataset."""

import argparse
import json
import shlex
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from prepare_yolox import convert_dataset
from runtime import CLASSES, ROOT, image_size, positive_int, run_name


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=ROOT / "data/coco-traffic", help="YOLO-format dataset")
    parser.add_argument(
        "--data", type=Path, default=ROOT / "data/coco-traffic-yolox", help="converted COCO-format dataset"
    )
    parser.add_argument("--yolox-dir", type=Path, default=ROOT / "third_party/YOLOX")
    parser.add_argument("--weights", type=Path, default=ROOT / "models/pretrained/yolox_nano.pth")
    parser.add_argument("--prepare-data", action="store_true", help="download the dataset first")
    parser.add_argument(
        "--prepare-only", action="store_true", help="convert the dataset and stop (no CUDA or YOLOX needed)"
    )
    parser.add_argument("--resume", type=Path, help="latest_ckpt.pth of an interrupted run")
    parser.add_argument("--epochs", type=int, default=50)
    parser.add_argument("--imgsz", type=image_size, default=320)
    parser.add_argument("--batch", type=positive_int, default=16)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--name", type=run_name, default="yolox-nano-traffic")
    parser.add_argument("--fp32", action="store_true", help="turn off mixed precision")
    args = parser.parse_args()
    if args.epochs < 2 or args.workers < 0:
        parser.error("--epochs must be at least 2 and --workers cannot be negative")

    run_dir = ROOT / "reports/training" / args.name
    if not args.prepare_only:
        if run_dir.exists() and not args.resume:
            parser.error("the run folder already exists: use --resume or a new --name")
        if args.resume and args.resume.resolve().parent != run_dir.resolve():
            parser.error("--resume must point into the run folder selected by --name")
        checkpoint = (args.resume or args.weights).resolve()
        if not checkpoint.is_file():
            parser.error(f"checkpoint not found: {checkpoint} (see docs/yolox.md)")
        if not (args.yolox_dir / "tools/train.py").is_file():
            parser.error("YOLOX source not found (see docs/yolox.md)")
        import torch

        if not torch.cuda.is_available():
            parser.error("CUDA is not available: this script needs a CUDA build of PyTorch on an NVIDIA machine")

    if args.prepare_data:
        download = [sys.executable, ROOT / "scripts/download_coco.py", "--output", args.source.resolve()]
        subprocess.run(list(map(str, download)), check=True)
    if not args.data.exists():
        convert_dataset(args.source, args.data)
    provenance = json.loads((args.data / "conversion.json").read_text())
    if provenance["source"] != str(args.source.resolve()) or provenance["classes"] != CLASSES:
        parser.error("the converted dataset was built from a different source or class list: choose another --data")
    for split in ("train2017", "val2017", "test2017"):
        if not (args.data / "annotations" / f"instances_{split}.json").is_file() or not (args.data / split).is_dir():
            parser.error(f"incomplete converted dataset: {args.data}")
    if args.prepare_only:
        print(f"Dataset ready: {args.data.resolve()}")
        return

    size = (args.imgsz, args.imgsz)
    overrides = {
        "data_dir": args.data.resolve(),
        "max_epoch": args.epochs,
        "input_size": size,
        "test_size": size,
        "random_size": (args.imgsz // 32, args.imgsz // 32),
        "warmup_epochs": min(5, max(0, args.epochs // 10)),
        "no_aug_epochs": min(10, max(1, args.epochs // 5)),
        "data_num_workers": args.workers,
    }
    # fmt: off
    command = [sys.executable, args.yolox_dir.resolve() / "tools/train.py",
               "-f", ROOT / "scripts/yolox/yolox_traffic_exp.py",
               "-d", 1, "-b", args.batch, "-expn", args.name, "-c", checkpoint]
    # fmt: on
    if args.resume:
        command.append("--resume")
    if not args.fp32:
        command.append("--fp16")
    for key, value in overrides.items():  # trailing KEY VALUE pairs understood by YOLOX
        command += [key, value]
    command = [str(part) for part in command]
    print(shlex.join(command), flush=True)
    subprocess.run(command, check=True, cwd=args.yolox_dir.resolve())

    # YOLOX logs training errors with loguru and can still exit with status 0.
    best, latest = run_dir / "best_ckpt.pth", run_dir / "latest_ckpt.pth"
    if not best.is_file() or not latest.is_file():
        raise RuntimeError(f"training produced no checkpoints, see {run_dir / 'train_log.txt'}")
    if torch.load(latest, map_location="cpu", weights_only=False).get("start_epoch", 0) < args.epochs:
        raise RuntimeError(f"training stopped early, see {run_dir / 'train_log.txt'}")
    print(f"Best weights: {best}\nExport with: python scripts/yolox/export_yolox.py --weights {best}")


if __name__ == "__main__":
    main()
