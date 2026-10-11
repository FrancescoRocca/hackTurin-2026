# System design

A pedestrian crossing built around an Arduino UNO Q. The board watches the crossing,
works out who is about to cross, and warns pedestrians and drivers. Vision runs locally on
the board.

## Components

| Part | Role |
| --- | --- |
| Thermal camera | Detects pedestrians about to cross. People are clearly hotter than the rest of the scene, so a classical computer vision step based on color blobs is enough; no neural network is involved. |
| RGB camera | Detects cars and bikes that are crossing or about to cross, using a YOLO object detector. |
| Buzzer | Audible signal that tells pedestrians, especially visually impaired ones, when to cross. |
| LED | Light signal that warns drivers that a pedestrian is on the road. |
| OLED display | Shows information about the state of the crossing. |

## This repository

Only the RGB detector lives here: dataset preparation, training of YOLO11n and YOLOX-Nano,
evaluation, ONNX export and the calibration data used for INT8 quantization in Edge Impulse.
See the [README](../README.md) to get started.
