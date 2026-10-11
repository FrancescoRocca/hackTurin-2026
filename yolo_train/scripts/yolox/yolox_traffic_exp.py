"""YOLOX-Nano experiment for the four-class traffic dataset.

Pass this file to YOLOX's tools/train.py with -f. Settings can be overridden with
trailing KEY VALUE arguments, e.g. `data_dir /workspace/data max_epoch 50`.
"""

from pathlib import Path

from yolox.exp.default.yolox_nano import Exp as NanoExp


class Exp(NanoExp):
    def __init__(self):
        super().__init__()
        root = Path(__file__).resolve().parents[2]
        self.exp_name = "yolox-nano-traffic"
        self.num_classes = 4
        self.data_dir = str(root / "data/coco-traffic-yolox")
        self.output_dir = str(root / "reports/training")
        self.input_size = self.test_size = (320, 320)
        # The Nano config sets random_size itself, so lowering multiscale_range alone
        # would still train at up to 640 px. Pin both to a single size.
        self.random_size = (10, 10)
        self.multiscale_range = 0
        self.max_epoch = 50
        self.warmup_epochs = 5
        self.no_aug_epochs = 10
        self.eval_interval = 1
        self.data_num_workers = 4
        self.save_history_ckpt = False
        self.seed = 42
        self.nmsthre = 0.45
