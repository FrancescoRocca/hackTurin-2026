"""Constants, argparse helpers and device checks shared by the scripts."""

import argparse
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CLASSES = ["car", "bicycle", "motorcycle", "pedestrian"]

# Keep Ultralytics settings in the project instead of the home directory.
(ROOT / ".ultralytics").mkdir(exist_ok=True)
os.environ.setdefault("YOLO_CONFIG_DIR", str(ROOT / ".ultralytics"))


def positive_int(value):
    number = int(value)
    if number < 1:
        raise argparse.ArgumentTypeError("must be a positive integer")
    return number


def image_size(value):
    size = int(value)
    if size < 32 or size % 32:
        raise argparse.ArgumentTypeError("must be a positive multiple of 32")
    return size


def probability(value):
    number = float(value)
    if not 0 <= number <= 1:
        raise argparse.ArgumentTypeError("must be between 0 and 1")
    return number


def run_name(value):
    if value in {"", ".", ".."} or Path(value).name != value:
        raise argparse.ArgumentTypeError("must be a single folder name")
    return value


def class_list(names):
    """Normalise the `names` entry of a YOLO data.yaml (dict or list) to a list."""
    if isinstance(names, dict):
        return [names.get(i, names.get(str(i))) for i in range(len(names))]
    return names


def require_mps():
    import torch

    if os.environ.get("PYTORCH_ENABLE_MPS_FALLBACK") == "1":
        raise RuntimeError("Unset PYTORCH_ENABLE_MPS_FALLBACK: unsupported ops must not fall back to the CPU silently.")
    if not torch.backends.mps.is_built() or not torch.backends.mps.is_available():
        raise RuntimeError(
            "Metal (MPS) is not available. Use a native arm64 Python on Apple silicon and run from a local terminal."
        )
    print(f"PyTorch {torch.__version__}, device: mps")
    return "mps"
