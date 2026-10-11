"""Export a YOLOX-Nano checkpoint to a static FP32 ONNX file (CPU) and write a model.json describing its I/O."""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from runtime import CLASSES, ROOT, image_size


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--weights", type=Path, default=ROOT / "reports/training/yolox-nano-traffic/best_ckpt.pth")
    parser.add_argument("--output", type=Path, default=ROOT / "models/edge-impulse/yolox-nano-traffic")
    parser.add_argument("--imgsz", type=image_size, default=320)
    parser.add_argument(
        "--decode", action="store_true", help="put grid/stride box decoding in the graph (default: raw YOLOX output)"
    )
    args = parser.parse_args()
    if not args.weights.is_file():
        parser.error(f"checkpoint not found: {args.weights}")
    if args.output.exists():
        parser.error("the output folder already exists: choose another --output")

    import numpy as np
    import onnx
    import onnxruntime as ort
    import torch

    from yolox_traffic_exp import Exp

    model = Exp().get_model().cpu().float().eval()
    checkpoint = torch.load(args.weights, map_location="cpu", weights_only=False)
    model.load_state_dict(checkpoint["model"], strict=True)
    model.head.decode_in_inference = args.decode

    args.output.mkdir(parents=True)
    target = args.output / "traffic.onnx"
    # YOLOX takes BGR float32 in 0..255, unlike the YOLO11 export (RGB, 0..1).
    generator = torch.Generator().manual_seed(42)
    sample = torch.rand((1, 3, args.imgsz, args.imgsz), generator=generator) * 255
    with torch.inference_mode():
        expected = model(sample).numpy()
        torch.onnx.export(
            model,
            sample,
            str(target),
            input_names=["images"],
            output_names=["output"],
            opset_version=13,
            dynamic_axes=None,
            dynamo=False,
        )

    # Check the graph and compare ONNX Runtime against PyTorch on the same random input.
    onnx.checker.check_model(str(target))
    session = ort.InferenceSession(str(target), providers=["CPUExecutionProvider"])
    actual = session.run(None, {"images": sample.numpy()})[0]
    anchors = sum((args.imgsz // stride) ** 2 for stride in (8, 16, 32))
    if session.get_inputs()[0].shape != [1, 3, args.imgsz, args.imgsz] or actual.shape != (1, anchors, 9):
        raise RuntimeError("unexpected ONNX input or output shape")
    np.testing.assert_allclose(actual, expected, rtol=1e-3, atol=1e-3)

    box_format = "boxes in input pixels" if args.decode else "raw box offsets, needs YOLOX grid/stride decoding"
    contract = {
        "architecture": "YOLOX-Nano",
        "weights": str(args.weights.resolve()),
        "classes": CLASSES,
        "input_shape": [1, 3, args.imgsz, args.imgsz],
        "output_shape": list(actual.shape),
        "dtype": "float32",
        "layout": "NCHW",
        "color": "BGR",
        "range": [0, 255],
        "resize": "aspect-preserving linear resize, image at the top-left, padding 114 on the right and bottom",
        "box_decoding_in_graph": args.decode,
        "output": f"cx, cy, w, h, objectness, then four class probabilities; {box_format}",
        "postprocessing": "score = objectness * class probability, per-class NMS, undo the resize",
        "verification": {
            "onnx_checker": "passed",
            "pytorch_onnx_parity": "passed",
            "max_abs_difference": float(np.abs(actual - expected).max()),
        },
    }
    (args.output / "model.json").write_text(json.dumps(contract, indent=2) + "\n")
    print(f"ONNX: {target}\nContract: {args.output / 'model.json'}")


if __name__ == "__main__":
    main()
