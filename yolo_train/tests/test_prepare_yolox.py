"""Tests for the YOLO -> COCO dataset conversion. No downloads, GPU or YOLOX install needed."""

import contextlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path

import yaml
from PIL import Image

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS / "yolox"))
sys.path.insert(0, str(SCRIPTS))

from prepare_yolox import convert_dataset
from runtime import CLASSES


class ConversionTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.source = Path(tmp.name) / "source"
        self.output = Path(tmp.name) / "converted"
        config = {"names": dict(enumerate(CLASSES))}
        for split in ("train", "val", "test"):
            config[split] = f"images/{split}"
            (self.source / "images" / split).mkdir(parents=True)
            (self.source / "labels" / split).mkdir(parents=True)
            Image.new("RGB", (200, 100)).save(self.source / "images" / split / f"{split}.jpg")
            (self.source / "labels" / split / f"{split}.txt").write_text("3 0.5 0.5 0.4 0.2\n")
        (self.source / "data.yaml").write_text(yaml.safe_dump(config))

    def convert(self):
        with contextlib.redirect_stdout(io.StringIO()):
            return convert_dataset(self.source, self.output)

    def load(self, name):
        return json.loads((self.output / "annotations" / f"instances_{name}.json").read_text())

    def test_boxes_class_ids_and_backgrounds(self):
        (self.source / "labels/test/test.txt").write_text("")
        self.convert()
        train, test = self.load("train2017"), self.load("test2017")

        self.assertEqual([c["name"] for c in train["categories"]], CLASSES)
        box = train["annotations"][0]
        self.assertEqual(box["category_id"], 4)
        for actual, expected in zip(box["bbox"], [60, 40, 80, 20], strict=True):
            self.assertAlmostEqual(actual, expected)
        self.assertAlmostEqual(box["area"], 1600)

        self.assertEqual(len(test["images"]), 1)
        self.assertEqual(test["annotations"], [])
        self.assertTrue((self.output / "train2017/train.jpg").is_file())

    def test_existing_output_is_not_overwritten(self):
        self.convert()
        with self.assertRaises(FileExistsError):
            self.convert()

    def test_missing_label_file(self):
        (self.source / "labels/val/val.txt").unlink()
        with self.assertRaises(FileNotFoundError):
            self.convert()
        self.assertFalse(self.output.exists())

    def test_non_finite_box(self):
        (self.source / "labels/train/train.txt").write_text("0 nan 0.5 0.2 0.2\n")
        with self.assertRaises(ValueError):
            self.convert()
        self.assertFalse(self.output.exists())

    def test_image_in_two_splits(self):
        (self.source / "images/val/val.jpg").rename(self.source / "images/val/train.jpg")
        with self.assertRaisesRegex(ValueError, "more than one split"):
            self.convert()

    def test_wrong_class_order(self):
        config = yaml.safe_load((self.source / "data.yaml").read_text())
        config["names"] = list(reversed(CLASSES))
        (self.source / "data.yaml").write_text(yaml.safe_dump(config))
        with self.assertRaisesRegex(ValueError, "Expected classes"):
            self.convert()


if __name__ == "__main__":
    unittest.main()
