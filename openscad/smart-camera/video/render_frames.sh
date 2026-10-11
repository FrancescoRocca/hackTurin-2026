#!/usr/bin/env bash
# Render the exploded-view clip frame by frame with OpenSCAD (4K, later
# downsampled to 1080p for anti-aliasing).  Run from smart-camera/.
#   video/render_frames.sh [fps=30] [jobs=4] [outdir=video/frames_4k]
set -euo pipefail
OS="${OPENSCAD:-$HOME/Downloads/OpenSCAD-2026.10.08-x86_64.AppImage}"
FPS="${1:-30}"; JOBS="${2:-4}"; OUT="${3:-video/frames_4k}"
cd "$(dirname "$0")/.."
T=$(sed -n 's/^T  *= *\([0-9.]*\);.*/\1/p' smart_camera_explode.scad | head -1)   # clip length, read from the .scad
N=$((T * FPS))
mkdir -p "$OUT"
export OS OUT N
render_one() {
  i=$1; f=$(printf '%s/f_%04d.png' "$OUT" "$i")
  [ -s "$f" ] && return 0
  ft=$(awk -v i="$i" -v n="$N" 'BEGIN{printf "%.9f", i/n}')
  "$OS" --projection=o --colorscheme=HackDark --imgsize=3840,2160 \
        -D "ft=$ft" -o "$f" smart_camera_explode.scad >/dev/null 2>&1
}
export -f render_one
seq 0 $((N - 1)) | xargs -P "$JOBS" -I{} bash -c 'render_one {}'
echo "done: $(ls "$OUT" | wc -l)/$N frames"
