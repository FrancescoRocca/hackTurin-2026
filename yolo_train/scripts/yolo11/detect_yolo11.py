"""Run YOLO11 on one image and save the annotated picture plus a JSON file with the detections."""

import argparse
import json
import sys
from pathlib import Path

from PIL import Image, ImageOps

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from runtime import ROOT, image_size, probability, require_mps


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--image", type=Path, required=True)
    parser.add_argument("--weights", type=Path, default=ROOT / "reports/training/yolo11n-traffic/weights/best.pt")
    parser.add_argument("--output", type=Path, default=ROOT / "outputs/detection.jpg")
    parser.add_argument("--conf", type=probability, default=0.25)
    parser.add_argument("--iou", type=probability, default=0.45)
    parser.add_argument("--imgsz", type=image_size, default=320)
    parser.add_argument("--device", choices=["mps", "cpu"], default="mps")
    parser.add_argument("--show", action="store_true", help="open the result in the system image viewer")
    args = parser.parse_args()
    if not args.image.is_file():
        parser.error(f"image not found: {args.image}")
    if not args.weights.is_file():
        parser.error(f"weights not found: {args.weights} (train a model first or pass --weights)")
    if args.output.resolve() in {args.image.resolve(), args.weights.resolve()}:
        parser.error("--output would overwrite the input image or the weights")
    if args.device == "mps":
        require_mps()
    from ultralytics import YOLO

    with Image.open(args.image) as opened:
        image = ImageOps.exif_transpose(opened).convert("RGB")
    model = YOLO(str(args.weights))
    result = model.predict(image, device=args.device, imgsz=args.imgsz, conf=args.conf, iou=args.iou, verbose=False)[0]

    annotated = Image.fromarray(result.plot()[..., ::-1])  # BGR -> RGB
    args.output.parent.mkdir(parents=True, exist_ok=True)
    annotated.save(args.output)

    detections = []
    for box in result.boxes.cpu():
        class_id = int(box.cls.item())
        detection = {
            "class_id": class_id,
            "label": result.names[class_id],
            "confidence": round(float(box.conf.item()), 5),
            "xyxy": [round(float(v), 2) for v in box.xyxy[0].tolist()],
        }
        detections.append(detection)
        print(f"{detection['label']:12} {detection['confidence']:.1%}  xyxy={detection['xyxy']}")
    if not detections:
        print("No detections above the confidence threshold.")

    summary = {
        "image": str(args.image.resolve()),
        "weights": str(args.weights.resolve()),
        "width": image.width,
        "height": image.height,
        "confidence_threshold": args.conf,
        "iou_threshold": args.iou,
        "speed_ms": result.speed,
        "detections": detections,
    }
    json_path = args.output.with_suffix(args.output.suffix + ".json")
    json_path.write_text(json.dumps(summary, indent=2) + "\n")
    print(f"Image: {args.output.resolve()}\nJSON:  {json_path.resolve()}")
    if args.show:
        annotated.show(title="Detections")


if __name__ == "__main__":
    main()
