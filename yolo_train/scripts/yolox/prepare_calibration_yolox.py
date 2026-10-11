"""Build calibration inputs for the YOLOX export: BGR float32 in 0..255, top-left letterbox."""

import sys
from pathlib import Path

import cv2

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from calibration_common import run
from preprocessing import letterbox


def make_preprocessor(height, width):
    def preprocess(path):
        image = cv2.imread(str(path))
        if image is None:
            raise ValueError(f"Cannot read {path}")
        canvas, _ = letterbox(image, height, width)
        return canvas.astype("float32")

    return preprocess


if __name__ == "__main__":
    run(
        "yolox",
        make_preprocessor,
        "BGR",
        [0, 255],
        "OpenCV BGR, top-left letterbox with padding 114 on right/bottom, linear resize, no normalization",
    )
