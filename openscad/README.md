# larp

Traffic counting node for hackTurin 2026. An Arduino UNO Q camera classifies what passes through an intersection on the device (cars, motorbikes, bicycles, pedestrians) and sends only counts and metadata to the network, never frames.

This repository contains the node hardware.

## Contents

| Path | Description |
|------|-------------|
| `smart-camera/` | 3D-printable enclosure (OpenSCAD), STL files, previews and assembly notes |
| `videos/smart-camera-explode/` | Exploded-view video of the node |

## Hardware

- Arduino UNO Q + UNO Media Carrier
- Sony IMX219 8MP camera
- Grove 16x2 LCD
- Grove RGB LED Ring (16 × WS2813 Mini)
- Grove Passive Buzzer

Dimensions, fasteners, print settings and items to check on the physical parts are in [`smart-camera/README.md`](smart-camera/README.md).

## License

See [`LICENSE`](LICENSE).
