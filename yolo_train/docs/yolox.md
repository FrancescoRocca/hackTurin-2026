# YOLOX-Nano

The same four-class dataset ([dataset.md](dataset.md)) trained with the official YOLOX
trainer on an NVIDIA GPU. Defaults: 320x320, 50 epochs, batch 16, mixed precision, seed 42,
validation every epoch, mosaic augmentation switched off for the last 10 epochs. The best
validation checkpoint is kept; the test split is never used to pick it.

## One command

On the training machine (Linux, NVIDIA driver for CUDA 12.4, [uv](https://docs.astral.sh/uv/)):

```sh
python3 scripts/yolox/remote_train.py
```

The script:

1. creates `.venv-yolox` with Python 3.11 and installs PyTorch 2.5.1 (CUDA 12.4) and the
   packages in `requirements-yolox.txt`;
2. clones YOLOX at a pinned commit into `third_party/YOLOX` and builds it;
3. downloads the pretrained Nano weights and the dataset, and converts the dataset;
4. trains, then exports the best checkpoint to ONNX.

Setup is skipped on later runs. If `git` or a C++ compiler is missing, the script installs
them when run as root on a system with apt. GPUs from the Blackwell generation need a newer
CUDA and PyTorch and are rejected. The pinned environment suits Ampere and Ada cards such as the RTX 3060.

```sh
python3 scripts/yolox/remote_train.py --setup-only             # install and check only
python3 scripts/yolox/remote_train.py --batch 8                # less GPU memory
python3 scripts/yolox/remote_train.py --epochs 2 --batch 4 --name yolox-nano-smoke
python3 scripts/yolox/remote_train.py --resume reports/training/yolox-nano-traffic/latest_ckpt.pth
```

`--skip-export` stops after training and `--fp32` turns off mixed precision. Run names are
not reused: after a finished run, use a new `--name`.

## Step by step

The same thing without the launcher, inside an activated Python 3.11 environment:

```sh
python -m pip install torch==2.5.1 torchvision==0.20.1 --index-url https://download.pytorch.org/whl/cu124
python -m pip install -r requirements-yolox.txt
git clone https://github.com/Megvii-BaseDetection/YOLOX.git third_party/YOLOX
git -C third_party/YOLOX checkout 6ddff4824372906469a7fae2dc3206c7aa4bbaee
python -m pip install --no-deps --no-build-isolation -e third_party/YOLOX
mkdir -p models/pretrained
curl -fL https://github.com/Megvii-BaseDetection/YOLOX/releases/download/0.1.1rc0/yolox_nano.pth \
  -o models/pretrained/yolox_nano.pth
```

Building YOLOX compiles the COCO evaluator, which needs `build-essential` and the Python
headers (`python3.11-dev`).

Then prepare the data and train:

```sh
python scripts/yolox/train_yolox.py --prepare-data
```

`--prepare-only` converts the dataset and stops, which is a cheap check before renting GPU
time. Conversion writes `data/coco-traffic-yolox/` with COCO-style annotations and symlinks
to the images, so the original dataset must stay where it is. It rejects missing labels,
malformed boxes and images that appear in two splits. COCO category ids are 1 to 4 and map
back to class indices 0 to 3.

`--imgsz` sets the training and validation size and turns multiscale training off. Larger
inputs will be slower on the UNO Q.

Artifacts go to `reports/training/<name>/`: `train_log.txt`, `best_ckpt.pth` and
`latest_ckpt.pth`. To resume, pass `--resume .../latest_ckpt.pth` with the same name,
epochs, batch and image size.

## Export

```sh
python scripts/yolox/export_yolox.py
```

Writes `models/edge-impulse/yolox-nano-traffic/traffic.onnx` and `model.json`. Use
`--weights` and `--output` for another run, and keep `--imgsz` equal to the training size.
The exporter checks the graph and compares ONNX Runtime against PyTorch on a fixed random
input.

YOLOX preprocessing is different from YOLO11:

- Input: float32 **BGR**, values 0 to **255**, aspect-preserving resize with the image in the
  top-left corner and padding 114 on the right and bottom.
- Output: `[1, 2100, 9]` at 320 px: four box values, objectness, four class probabilities.
  The score is objectness times class probability.
- By default the box values are raw offsets that need YOLOX grid/stride decoding.
  `--decode` puts the decoding in the graph and returns boxes in input pixels; then the
  consumer must not decode again.
- Neither variant contains NMS.

Do not reuse the YOLO11 import settings or its calibration file. Check what the Edge Impulse
YOLOX decoder expects (raw or decoded output, preprocessing) before importing. Conversion
and on-board latency have not been validated for this model.

## Calibration data for INT8

```sh
uv run python scripts/yolox/prepare_calibration_yolox.py \
  --model models/edge-impulse/yolox-nano-traffic/traffic.onnx \
  --images data/coco-traffic/images/val --samples 100 \
  --output models/edge-impulse/yolox-nano-traffic/representative-features.npy
```

Produces a float32 `[100, 3, 320, 320]` array with the YOLOX preprocessing above and a JSON
manifest with the image list and the ONNX hash. Upload it together with that exact ONNX file
as representative features. The script refuses to overwrite files and checks `model.json`
for mismatched preprocessing. Evaluate the INT8 model afterwards on images outside the
calibration set.

## Evaluating the ONNX file

The exported model can be evaluated on any machine, without CUDA or a YOLOX install:

```sh
uv run --with pycocotools python scripts/yolox/evaluate_yolox.py \
  --model models/edge-impulse/yolox-nano-traffic/traffic.onnx
```

`model.json` has to stay next to the ONNX file. The script runs ONNX Runtime on the CPU
over the test split with per-class NMS and reports COCO mAP50, mAP50-95, average recall and
per-class AP in `reports/evaluation/yolox-onnx-test/` (use `--output` for another folder,
`--split val` while tuning, `--limit 20` for a quick check).

The score floor is 0.001 on purpose, because AP needs the whole confidence range. It is not
a deployment threshold. As with YOLO11, these scores describe the COCO subset, not the real
camera, and CPU timing does not carry over to the UNO Q.

## References

- [YOLOX: training on custom data](https://github.com/Megvii-BaseDetection/YOLOX/blob/main/docs/train_custom_data.md)
- [YOLOX-Nano experiment](https://github.com/Megvii-BaseDetection/YOLOX/blob/main/exps/default/yolox_nano.py)
- [YOLOX ONNX Runtime demo](https://github.com/Megvii-BaseDetection/YOLOX/blob/main/demo/ONNXRuntime/README.md)
