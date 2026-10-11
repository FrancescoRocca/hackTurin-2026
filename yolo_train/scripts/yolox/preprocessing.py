"""Native YOLOX preprocessing, shared by the evaluation and calibration scripts."""

import cv2
import numpy as np


def letterbox(image, height, width):
    """Resize keeping the aspect ratio and paste into the top-left of a gray (114) canvas.

    Takes and returns BGR uint8 images, plus the scale factor that was applied.
    """
    ratio = min(height / image.shape[0], width / image.shape[1])
    size = (int(image.shape[1] * ratio), int(image.shape[0] * ratio))
    resized = cv2.resize(image, size, interpolation=cv2.INTER_LINEAR)
    canvas = np.full((height, width, 3), 114, dtype=np.uint8)
    canvas[: resized.shape[0], : resized.shape[1]] = resized
    return canvas, ratio
