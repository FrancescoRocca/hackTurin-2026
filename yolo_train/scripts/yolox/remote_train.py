#!/usr/bin/env python3
"""Set up a Linux/NVIDIA machine, download the dataset, train YOLOX-Nano and export it to ONNX.

    python3 scripts/yolox/remote_train.py

Needs only the standard library and uv to start; everything else is installed
into .venv-yolox.
"""

import argparse
import hashlib
import json
import os
import shlex
import shutil
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from runtime import ROOT, image_size, positive_int, run_name

YOLOX_REPOSITORY = "https://github.com/Megvii-BaseDetection/YOLOX.git"
YOLOX_REVISION = "6ddff4824372906469a7fae2dc3206c7aa4bbaee"
WEIGHTS_URL = "https://github.com/Megvii-BaseDetection/YOLOX/releases/download/0.1.1rc0/yolox_nano.pth"
TORCH_INDEX = "https://download.pytorch.org/whl/cu124"
ENVIRONMENT = ROOT / ".venv-yolox"


def run(command, **kwargs):
    print("\n$ " + shlex.join(map(str, command)), flush=True)
    return subprocess.run(list(map(str, command)), check=True, cwd=ROOT, **kwargs)


def download_weights(target):
    if target.is_file():
        return
    target.parent.mkdir(parents=True, exist_ok=True)
    partial = target.with_suffix(".pth.part")
    for attempt in range(4):
        try:
            print(f"Downloading pretrained weights to {target}", flush=True)
            request = urllib.request.Request(WEIGHTS_URL, headers={"User-Agent": "uno-q-yolox/1.0"})
            with urllib.request.urlopen(request, timeout=120) as response, partial.open("wb") as out:
                shutil.copyfileobj(response, out)
            if partial.stat().st_size < 100_000:
                raise RuntimeError("the downloaded weights file is too small")
            partial.replace(target)
            return
        except Exception:
            if attempt == 3:
                raise
            time.sleep(2**attempt)


def check_machine():
    if sys.platform != "linux":
        raise RuntimeError("this script is meant for a Linux machine with an NVIDIA GPU")
    if not shutil.which("uv"):
        raise RuntimeError("uv is not installed or not on PATH")
    if not shutil.which("nvidia-smi"):
        raise RuntimeError("no NVIDIA driver found (nvidia-smi is missing)")
    query = ["nvidia-smi", "--query-gpu=name,compute_cap", "--format=csv,noheader"]
    gpus = subprocess.check_output(query, text=True).strip()
    print(f"GPU: {gpus}", flush=True)
    for line in gpus.splitlines():
        if float(line.rsplit(",", 1)[1]) >= 10:
            raise RuntimeError("Blackwell GPUs need CUDA 12.8+, but this setup pins PyTorch for CUDA 12.4")


def install_build_tools():
    """Install git and a C++ compiler (needed to build YOLOX's COCO evaluator) if they are missing."""
    if shutil.which("git") and shutil.which("g++"):
        return
    if os.geteuid() != 0 or not shutil.which("apt-get"):
        raise RuntimeError("git and a C++ compiler are required: install them and run again")
    run(["apt-get", "update"])
    run(["apt-get", "install", "-y", "git", "build-essential"])


def checkout_yolox():
    source = ROOT / "third_party/YOLOX"
    if not source.exists():
        source.parent.mkdir(parents=True, exist_ok=True)
        run(["git", "clone", YOLOX_REPOSITORY, source])
        run(["git", "-C", source, "checkout", YOLOX_REVISION])
    head = subprocess.check_output(["git", "-C", str(source), "rev-parse", "HEAD"], text=True).strip()
    if head != YOLOX_REVISION:
        raise RuntimeError(f"{source} is at {head}, expected {YOLOX_REVISION}: use a clean checkout")
    return source


CUDA_CHECK = """
import torch, torchvision, yolox, onnx, onnxruntime, yaml, PIL
from yolox.layers import fast_cocoeval
assert torch.cuda.is_available(), 'CUDA is not available'
x = torch.ones(16, device='cuda')
assert x.sum().item() == 16
print('CUDA OK:', torch.cuda.get_device_name(0), '| PyTorch', torch.__version__)
"""

CHECKPOINT_CHECK = """
import sys, torch
checkpoint = torch.load(sys.argv[1], map_location='cpu', weights_only=False)
assert isinstance(checkpoint, dict) and 'model' in checkpoint
print('Pretrained checkpoint OK')
"""


def setup():
    check_machine()
    install_build_tools()
    uv = shutil.which("uv")
    python = ENVIRONMENT / "bin/python"
    if not python.is_file():
        run([uv, "venv", "--python", "3.11", ENVIRONMENT])
    source = checkout_yolox()

    def pip_install(*arguments, **kwargs):
        run([uv, "pip", "install", "--python", python, *arguments], **kwargs)

    # Reinstall whenever the requirements or the pinned versions change.
    pins = f"{YOLOX_REVISION}-torch2.5.1-torchvision0.20.1-cu124-python3.11"
    fingerprint = hashlib.sha256((ROOT / "requirements-yolox.txt").read_bytes() + pins.encode()).hexdigest()
    marker = ENVIRONMENT / "setup.json"
    if not marker.is_file() or json.loads(marker.read_text()).get("fingerprint") != fingerprint:
        pip_install("setuptools<81", "wheel", "packaging")
        pip_install("torch==2.5.1", "torchvision==0.20.1", "--index-url", TORCH_INDEX)
        pip_install("-r", ROOT / "requirements-yolox.txt")
        build_env = {**os.environ}
        build_env.setdefault("MAX_JOBS", "2")
        pip_install("--no-deps", "--no-build-isolation", "-e", source, env=build_env)

    run([python, "-c", CUDA_CHECK])
    weights = ROOT / "models/pretrained/yolox_nano.pth"
    download_weights(weights)
    run([python, "-c", CHECKPOINT_CHECK, weights])
    marker.write_text(json.dumps({"fingerprint": fingerprint, "yolox_revision": YOLOX_REVISION}, indent=2) + "\n")
    return python


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--setup-only", action="store_true", help="install and verify everything, then stop")
    parser.add_argument("--epochs", type=int, default=50)
    parser.add_argument("--batch", type=positive_int, default=16)
    parser.add_argument("--imgsz", type=image_size, default=320)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--name", type=run_name, default="yolox-nano-traffic")
    parser.add_argument("--resume", type=Path, help="latest_ckpt.pth of an interrupted run")
    parser.add_argument("--fp32", action="store_true", help="turn off mixed precision")
    parser.add_argument("--skip-export", action="store_true", help="do not export to ONNX after training")
    args = parser.parse_args()
    if args.epochs < 2 or args.workers < 0:
        parser.error("--epochs must be at least 2 and --workers cannot be negative")

    run_dir = ROOT / "reports/training" / args.name
    export_dir = ROOT / "models/edge-impulse" / args.name
    if not args.setup_only:
        if run_dir.exists() and not args.resume:
            parser.error("the run already exists: use --resume or a new --name")
        if not args.skip_export and export_dir.exists():
            parser.error("the export folder already exists: use a new --name or --skip-export")
        if args.resume and (not args.resume.is_file() or args.resume.resolve().parent != run_dir.resolve()):
            parser.error("--resume must be a checkpoint inside the run selected by --name")

    python = setup()
    if args.setup_only:
        print("\nSetup complete.")
        return

    # fmt: off
    train = [python, ROOT / "scripts/yolox/train_yolox.py", "--prepare-data",
             "--epochs", args.epochs, "--batch", args.batch, "--imgsz", args.imgsz,
             "--workers", args.workers, "--name", args.name]
    # fmt: on
    if args.resume:
        train += ["--resume", args.resume.resolve()]
    if args.fp32:
        train.append("--fp32")
    run(train)

    best = run_dir / "best_ckpt.pth"
    if not args.skip_export:
        export = ROOT / "scripts/yolox/export_yolox.py"
        run([python, export, "--weights", best, "--output", export_dir, "--imgsz", args.imgsz])
    print(f"\nDone. Best checkpoint: {best}", flush=True)


if __name__ == "__main__":
    try:
        main()
    except (RuntimeError, subprocess.CalledProcessError) as error:
        print(f"\nError: {error}", file=sys.stderr)
        sys.exit(1)
