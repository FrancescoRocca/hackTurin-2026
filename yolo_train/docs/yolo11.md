# YOLO11n

Four classes (see [dataset.md](dataset.md)), 320x320 input, trained on Apple Metal and
exported to FP32 ONNX. All commands run from the repository root after `uv sync --locked`.

## Training

```sh
uv run python scripts/yolo11/train_yolo11.py --prepare-data --name yolo11n-traffic
```

This builds the dataset if needed, downloads the pretrained `yolo11n.pt` into
`models/pretrained/`, trains for 50 epochs and exports the best checkpoint. Defaults:
batch 16, seed 42, no early stopping, AMP off, dataloader workers 0. Try batch 8 or 4 if
memory runs out.

The script stops if Metal is unavailable or if `PYTORCH_ENABLE_MPS_FALLBACK=1` is set,
so training never falls back to the CPU without telling you. Run names are never reused:
if the run or export folder exists, pick a new `--name`.

Output:

```
reports/training/<name>/             weights, curves, plots, pipeline.json
models/edge-impulse/<name>/          traffic.onnx and model.json
```

Because early stopping is off, the exported weights are the best validation checkpoint,
not necessarily the last epoch.

### Fine-tuning and resuming

`finetune_yolo11.py` trains without exporting and exposes more options:

```sh
uv run python scripts/yolo11/finetune_yolo11.py \
  --model reports/training/yolo11n-traffic/weights/best.pt \
  --optimizer AdamW --lr0 0.0001 --name yolo11n-traffic-finetune
```

To continue an interrupted run:

```sh
uv run python scripts/yolo11/finetune_yolo11.py --resume reports/training/<name>/weights/last.pt
```

Export separately afterwards (below).

## Evaluation and inference

```sh
uv run python scripts/yolo11/evaluate_yolo11.py --name yolo11n-traffic-test
uv run python scripts/yolo11/detect_yolo11.py --image path/to/photo.jpg --show
```

Evaluation uses the test split by default (`--split val` for the validation split) and
writes `summary.json` with the metrics, per-class mAP50-95 and a confusion matrix computed
at confidence 0.25. Detection uses confidence 0.25 and NMS IoU 0.45.

## Export

`train_yolo11.py` exports automatically. To export a checkpoint yourself:

```sh
uv run python scripts/yolo11/export_yolo11.py \
  --weights reports/training/yolo11n-traffic/weights/best.pt \
  --output models/edge-impulse/yolo11n-traffic
```

The export is FP32, opset 13, static batch 1, without NMS or simplification. The script
checks the graph before writing `model.json`.

- Input: float32 RGB `[1, 3, 320, 320]`, aspect-preserving letterbox with padding 114,
  divided by 255.
- Output: `[1, 8, 2100]`. The first four channels are `cx, cy, w, h` in input pixels, the
  other four are the class probabilities. There is no objectness channel.

## Calibration data for INT8

Edge Impulse can quantize the model if you upload a sample of real, preprocessed inputs
next to the ONNX file:

```sh
uv run python scripts/yolo11/prepare_calibration_yolo11.py \
  --model models/edge-impulse/yolo11n-traffic/traffic.onnx \
  --images data/coco-traffic/images/train --samples 100 \
  --output models/edge-impulse/yolo11n-traffic/representative-features.npy
```

This writes 100 randomly chosen training images (seed 42) as a float32 array of shape
`[100, 3, 320, 320]` (about 117 MiB), preprocessed exactly like the export input, plus a
JSON manifest with the image list and the hash of the ONNX file. Regenerate it whenever
the ONNX changes. No labels are needed, and the script does not run or quantize the model.

## Edge Impulse import

Upload the `.onnx` with the "Bring your own model" flow, and the `.npy` as representative
features if you want INT8.

| Setting | Value |
| --- | --- |
| Target | Arduino UNO Q (Qualcomm QRB2210) |
| Input | Image, RGB, 320x320 |
| Pixel range | 0 to 1, no further normalization |
| Resize | Fit longest axis (pre-letterbox to 320x320 with padding 114 to match training exactly) |
| Output | Object detection, YOLOv11 (coordinates in absolute values) |
| Classes | 4, in this order: `car,bicycle,motorcycle,pedestrian` |

Edge Impulse may show the input as NHWC `[1, 320, 320, 3]` after conversion; leave the ONNX
as it is. Compare the INT8 detections with the FP32 ones on images that were not used for
calibration, and measure latency on the board. Neither has been checked in this repository.

## References

- [Ultralytics YOLO11](https://docs.ultralytics.com/models/yolo11/)
- [Ultralytics export](https://docs.ultralytics.com/modes/export/)
- [Edge Impulse BYOM](https://docs.edgeimpulse.com/studio/projects/dashboard/byom)
- [Edge Impulse on the UNO Q](https://docs.edgeimpulse.com/hardware/boards/arduino-uno-q)
