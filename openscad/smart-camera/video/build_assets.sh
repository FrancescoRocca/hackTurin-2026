#!/usr/bin/env bash
# Compile the assembled-position meshes used by smart_camera_explode.scad
# from scratch (manifold backend).  Run from smart-camera/.
set -euo pipefail
OS="${OPENSCAD:-$HOME/Downloads/OpenSCAD-2026.10.08-x86_64.AppImage}"
cd "$(dirname "$0")/.."
mkdir -p video/stl
for p in body lid retainer clamp_usb clamp_inner; do
  echo ">> $p"
  "$OS" --backend=manifold -D 'asm="'$p'"' -D 'use_mesh=false' \
        -o "video/stl/${p}_asm.stl" smart_camera_explode.scad
done
ls -la video/stl
