"""Build calibration inputs for the YOLO11 export: RGB float32 in 0..1, centered letterbox."""

import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageOps

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import runtime  # noqa: F401  (points Ultralytics at the project config dir before it is imported)
from calibration_common import run


def make_preprocessor(height, width):
    from ultralytics.data.augment import LetterBox

    letterbox = LetterBox(
        new_shape=(height, width), auto=False, scale_fill=False, scaleup=True, center=True, padding_value=114
    )

    def preprocess(path):
        with Image.open(path) as image:
            rgb = np.array(ImageOps.exif_transpose(image).convert("RGB"))
        return letterbox(image=rgb).astype(np.float32) / np.float32(255)

    return preprocess


if __name__ == "__main__":
    run(
        "yolo11",
        make_preprocessor,
        "RGB",
        [0, 1],
        "EXIF correction, centered letterbox with padding 114, linear resize, /255",
    )
