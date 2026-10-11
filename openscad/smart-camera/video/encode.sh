#!/usr/bin/env bash
# 4K OpenSCAD frames -> 1080p H.264 (the downscale is the anti-aliasing pass).
set -euo pipefail
cd "$(dirname "$0")/.."
OUT="${1:-../videos/smart-camera-explode/assets/explode.mp4}"
mkdir -p "$(dirname "$OUT")"
ffmpeg -y -loglevel error -framerate 30 -i video/frames_4k/f_%04d.png \
  -vf "scale=1920:1080:flags=area" \
  -c:v libx264 -preset slow -crf 13 -g 30 -pix_fmt yuv420p -movflags +faststart "$OUT"
ls -la "$OUT"
