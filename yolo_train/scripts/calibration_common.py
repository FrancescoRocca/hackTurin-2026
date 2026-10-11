"""Shared logic for the calibration scripts: ONNX input checks, image sampling, .npy output."""

import argparse
import hashlib
import json
import random
from pathlib import Path

import numpy as np
import onnx

IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".bmp", ".webp", ".tif", ".tiff"}


def model_input(path):
    """Return (name, shape, layout) of the single static float32 image input of an ONNX file."""
    graph = onnx.load(str(path)).graph
    initializers = {tensor.name for tensor in graph.initializer}
    inputs = [tensor for tensor in graph.input if tensor.name not in initializers]
    if len(inputs) != 1 or inputs[0].type.tensor_type.elem_type != onnx.TensorProto.FLOAT:
        raise ValueError("expected a single float32 image input")
    shape = [dim.dim_value for dim in inputs[0].type.tensor_type.shape.dim]
    if len(shape) != 4 or shape[0] != 1 or min(shape) < 1:
        raise ValueError(f"expected a static batch-1 image input, got {shape}")
    if shape[1] == 3 and shape[-1] != 3:
        layout = "NCHW"
    elif shape[-1] == 3 and shape[1] != 3:
        layout = "NHWC"
    else:
        raise ValueError(f"cannot find the three-channel axis in input {shape}")
    return inputs[0].name, shape, layout


def check_contract(model, preprocessing):
    """Reject a model whose export metadata (model.json) belongs to the other architecture."""
    path = model.with_name("model.json")
    contract = json.loads(path.read_text()) if path.is_file() else {}
    detected = None
    if contract.get("architecture") == "YOLOX-Nano":
        detected = "yolox"
    elif "yolo11" in contract.get("model_config", "").lower():
        detected = "yolo11"
    if detected not in (None, preprocessing):
        raise ValueError(f"model.json describes a {detected} export, not {preprocessing}")
    if preprocessing == "yolox" and contract and (contract.get("color") != "BGR" or contract.get("range") != [0, 255]):
        raise ValueError("expected a native YOLOX export (BGR, 0..255)")


def run(preprocessing, make_preprocessor, color, value_range, description):
    parser = argparse.ArgumentParser(
        description=f"Build Edge Impulse representative features for a {preprocessing} ONNX export."
    )
    parser.add_argument("--model", type=Path, required=True, help="the exact ONNX file that will be uploaded")
    parser.add_argument("--images", type=Path, required=True, help="directory with representative images")
    parser.add_argument("--samples", type=int, required=True, help="number of images to sample")
    parser.add_argument("--output", type=Path, required=True, help="destination .npy file")
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()
    if not args.model.is_file() or not args.images.is_dir():
        parser.error("model file and image directory must exist")
    if args.samples < 1 or args.output.suffix != ".npy":
        parser.error("--samples must be positive and --output must end in .npy")

    output = args.output.resolve()
    manifest_path = output.with_suffix(".json")
    temporary = output.with_suffix(".npy.part")
    if output.exists() or manifest_path.exists() or temporary.exists():
        parser.error("output, its manifest or a partial file already exists; choose a new --output")
    try:
        check_contract(args.model, preprocessing)
        input_name, shape, layout = model_input(args.model)
    except ValueError as error:
        parser.error(str(error))
    height, width = shape[2:] if layout == "NCHW" else shape[1:3]

    images = sorted({p.resolve() for p in args.images.rglob("*") if p.is_file() and p.suffix.lower() in IMAGE_SUFFIXES})
    if len(images) < args.samples:
        parser.error(f"asked for {args.samples} images but found {len(images)}")
    selected = random.Random(args.seed).sample(images, args.samples)
    preprocess = make_preprocessor(height, width)

    # The first axis indexes calibration images and replaces the model's batch of 1.
    calibration_shape = (args.samples, *shape[1:])
    size_mb = np.prod(calibration_shape) * 4 / 1e6
    print(f"ONNX input: {input_name} {shape} {layout}")
    print(f"Calibration: {calibration_shape}, float32 {color} {value_range}, {size_mb:.1f} MB", flush=True)

    output.parent.mkdir(parents=True, exist_ok=True)
    features = np.lib.format.open_memmap(temporary, mode="w+", dtype=np.float32, shape=calibration_shape)
    low, high = float("inf"), float("-inf")
    try:
        for index, path in enumerate(selected):
            pixels = preprocess(path)
            if layout == "NCHW":
                pixels = pixels.transpose(2, 0, 1)
            if pixels.shape != tuple(shape[1:]) or not np.isfinite(pixels).all():
                raise ValueError(f"invalid preprocessed image: {path}")
            low, high = min(low, float(pixels.min())), max(high, float(pixels.max()))
            features[index] = pixels
            if (index + 1) % 25 == 0 or index + 1 == len(selected):
                print(f"Prepared {index + 1}/{len(selected)} images", flush=True)
        features.flush()
    except BaseException:
        del features
        temporary.unlink(missing_ok=True)
        raise
    del features
    temporary.replace(output)

    with args.model.open("rb") as source:
        model_hash = hashlib.file_digest(source, "sha256").hexdigest()
    manifest = {
        "model": str(args.model.resolve()),
        "model_sha256": model_hash,
        "input_name": input_name,
        "model_input_shape": shape,
        "calibration_shape": list(calibration_shape),
        "layout": layout,
        "dtype": "float32",
        "color": color,
        "range": value_range,
        "observed_range": [low, high],
        "preprocessing_mode": preprocessing,
        "preprocessing": description,
        "seed": args.seed,
        "source_directory": str(args.images.resolve()),
        "images": [str(path) for path in selected],
        "note": "Raw preprocessed inputs, no labels or augmentation. Measure quantized accuracy separately.",
    }
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")
    print(f"Representative features: {output}\nManifest: {manifest_path}")
