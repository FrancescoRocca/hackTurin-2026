"""Export a YOLO11 checkpoint to a static FP32 ONNX file and write a model.json describing its I/O."""

import argparse
import json
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from runtime import ROOT, image_size


def dims(tensor):
    return [dim.dim_value or dim.dim_param for dim in tensor.type.tensor_type.shape.dim]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--weights", type=Path, default=ROOT / "reports/training/yolo11n-traffic/weights/best.pt")
    parser.add_argument("--output", type=Path, default=ROOT / "models/edge-impulse/yolo11n-traffic")
    parser.add_argument("--imgsz", type=image_size, default=320)
    parser.add_argument("--filename", default="traffic.onnx", help="ONNX file name inside --output")
    args = parser.parse_args()
    if not args.weights.is_file():
        parser.error(f"weights not found: {args.weights}")
    if Path(args.filename).name != args.filename or not args.filename.endswith(".onnx"):
        parser.error("--filename must be a plain file name ending in .onnx")

    import onnx
    from ultralytics import YOLO

    model = YOLO(str(args.weights))
    exported = Path(
        model.export(
            format="onnx",
            device="cpu",
            imgsz=args.imgsz,
            batch=1,
            half=False,
            dynamic=False,
            simplify=False,
            nms=False,
            opset=13,
        )
    )
    graph = onnx.load(str(exported))
    onnx.checker.check_model(graph)

    if len(graph.graph.input) != 1 or dims(graph.graph.input[0]) != [1, 3, args.imgsz, args.imgsz]:
        raise ValueError("expected one static NCHW input")
    if len(graph.graph.output) != 1:
        raise ValueError("expected one detection output")
    output_shape = dims(graph.graph.output[0])
    if len(output_shape) != 3 or output_shape[:2] != [1, 4 + len(model.names)] or not isinstance(output_shape[2], int):
        raise ValueError(f"unexpected output shape: {output_shape}")
    if any(t.type.tensor_type.elem_type != onnx.TensorProto.FLOAT for t in [*graph.graph.input, *graph.graph.output]):
        raise ValueError("expected float32 inputs and outputs")

    args.output.mkdir(parents=True, exist_ok=True)
    target = args.output / args.filename
    if exported.resolve() != target.resolve():
        shutil.move(str(exported), target)

    contract = {
        "architecture": "Ultralytics YOLO detection",
        "model_config": str(model.model.yaml.get("yaml_file", "unknown")),
        "weights": str(args.weights.resolve()),
        "classes": model.names,
        "inputs": {t.name: dims(t) for t in graph.graph.input},
        "outputs": {t.name: dims(t) for t in graph.graph.output},
        "input": {
            "dtype": "float32",
            "layout": "NCHW",
            "color": "RGB",
            "range": [0, 1],
            "resize": "aspect-preserving letterbox to a square, padding RGB=(114,114,114), divide by 255",
        },
        "output": "[1, 4 + num_classes, anchors]: cx, cy, w, h in input pixels, then class scores (no objectness)",
        "postprocessing": "pick the best class, per-class NMS, undo the letterbox, clip to the image",
        "edge_impulse": "BYOM, object detection, YOLOv11 (coordinates in absolute values), RGB pixels 0..1",
    }
    (args.output / "model.json").write_text(json.dumps(contract, indent=2) + "\n")
    print(f"ONNX: {target.resolve()}\nContract: {(args.output / 'model.json').resolve()}")


if __name__ == "__main__":
    main()
