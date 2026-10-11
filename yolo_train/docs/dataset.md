# Dataset

Both models are trained on a subset of COCO 2017 with four classes. The order is fixed
and every script checks it:

| ID | Label | COCO class |
| --- | --- | --- |
| 0 | car | car |
| 1 | bicycle | bicycle |
| 2 | motorcycle | motorcycle |
| 3 | pedestrian | person (includes riders and seated people) |

## Building it

```sh
uv run python scripts/download_coco.py --output data/coco-traffic
```

The script downloads the Ultralytics COCO label files, picks the images and downloads only
those from the COCO servers. It is safe to interrupt and run again.

- **Train**: 1,500 images per class from COCO train2017. An image that contains several
  classes counts for each of them, so the total is somewhat higher than 4 x 1,500.
- **Validation**: 10% of train2017, split off by image before sampling so that no image
  appears in both sets.
- **Test**: 500 images per class from COCO val2017.
- **Backgrounds**: images without any target object, added at 15% of the number of
  positive images in each split.

Every target box on a selected image is kept, not only those of the class the image was
sampled for. Sampling balances images, not boxes. Related options: `--per-class`,
`--test-per-class`, `--negative-ratio`, `--val-fraction`, `--workers`, `--seed`.

The output folder contains `images/{train,val,test}`, `labels/{train,val,test}`, a
`data.yaml` for Ultralytics, and `manifest.json` with the settings, image ids and the hash
of the label archive. Running the script again with different settings on the same folder
is refused; use another `--output`.

## Reading the results

- COCO-pretrained YOLO11 weights have already seen train2017, so the validation split is
  not independent of the pretraining.
- The test images come from val2017, which Ultralytics also uses to evaluate the
  pretrained weights.
- The upstream label conversion leaves out crowd annotations.
- Scores from different subsets or class selections cannot be compared directly.

For a realistic figure, annotate frames from the camera that will be installed and
evaluate on those.

## Comparing runs

Use the validation split while tuning and keep the test split for the final comparison:

```sh
uv run python scripts/yolo11/evaluate_yolo11.py --split val --name run-a-val
uv run python scripts/yolo11/evaluate_yolo11.py --split val --weights reports/training/run-b/weights/best.pt --name run-b-val
```

Look at per-class AP, recall and the confusion matrix, not only the aggregate mAP.
