# UNO Q traffic detector

Object detection models for a smart pedestrian crossing built on the Arduino UNO Q.
The camera has to tell cars, bicycles, motorcycles and pedestrians apart, and it has
to do it on the board itself. This repository holds the training, evaluation and
export code for those models; the rest of the system is described in
[docs/system-design.md](docs/system-design.md).

Two detectors are trained on the same four-class COCO subset at 320x320:

- **YOLO11n** (Ultralytics), trained on a Mac with Apple Metal.
- **YOLOX-Nano**, trained on a rented NVIDIA GPU.

Both are exported to ONNX and imported into Edge Impulse for the UNO Q.

## Layout

```
docs/         dataset, per-model guides and system design
scripts/
  download_coco.py        builds the dataset
  calibration_common.py   shared code of the two calibration scripts
  runtime.py              shared constants and argparse helpers
  yolo11/                 train, fine-tune, evaluate, export, detect, calibrate
  yolox/                  same for YOLOX, plus remote_train.py (one-command setup + training)
tests/        tests for the dataset conversion
```

Datasets, weights and reports are generated locally and ignored by Git.

## Quick start (YOLO11, macOS)

Requires Python 3.12 and [uv](https://docs.astral.sh/uv/). Run everything from the repository root.

```sh
uv sync --locked

# download the dataset, train for 50 epochs and export the best checkpoint to ONNX
uv run python scripts/yolo11/train_yolo11.py --prepare-data

# run the trained model on any photo
uv run python scripts/yolo11/detect_yolo11.py --image path/to/photo.jpg --show
```

The detection script writes `outputs/detection.jpg` and a JSON file with the boxes
(pixel `xyxy` coordinates in the original image). Pass `--device cpu` to run without Metal.

## Quick start (YOLOX, Linux with NVIDIA GPU)

```sh
python3 scripts/yolox/remote_train.py
```

This creates a Python 3.11 environment, installs CUDA PyTorch and YOLOX, downloads the
data and the pretrained weights, trains, and exports to ONNX. See [docs/yolox.md](docs/yolox.md).

## Results (YOLO11n, test split)

| Metric | Value |
| --- | ---: |
| Precision | 66.5% |
| Recall | 40.0% |
| mAP50 | 46.1% |
| mAP50-95 | 26.6% |

mAP50-95 per class: car 21.5%, bicycle 20.0%, motorcycle 33.9%, pedestrian 31.0%.

The model was trained for 50 epochs and the best checkpoint (epoch 49) was exported.
These numbers come from a held-out part of COCO, not from the real camera, and the timing
measured on a Mac says nothing about the UNO Q. Accuracy on footage from the crossing
still has to be measured.

Reproduce with:

```sh
uv run python scripts/yolo11/evaluate_yolo11.py --name yolo11n-traffic-test
```

## Documentation

- [docs/system-design.md](docs/system-design.md): the full crossing system
- [docs/dataset.md](docs/dataset.md): how the dataset is built and what to keep in mind when reading the results
- [docs/yolo11.md](docs/yolo11.md): training, export, calibration and Edge Impulse settings for YOLO11
- [docs/yolox.md](docs/yolox.md): the same for YOLOX-Nano

## Tests

```sh
uv run python -m unittest discover -s tests
```

## License

Released under the [GNU AGPL-3.0](LICENSE), the license of the Ultralytics library the
YOLO11 scripts depend on. YOLOX is Apache-2.0.
