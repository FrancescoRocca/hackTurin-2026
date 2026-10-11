# Smart Camera — Enclosure (Arduino UNO Q)

Enclosure for the smart camera: Arduino UNO Q + UNO Media Carrier + Sony IMX219 8MP camera + Grove 16x2 LCD + Grove RGB LED Ring (16-WS2813 Mini) + Grove Passive Buzzer.

The plan is a pentagon: a square box with the front vertical corner cut off.
- **Chamfered face (front)**: camera opening centred between the four mounting holes, at height 53.85 mm; points forward.
- **Buzzer**: Grove Passive Buzzer (20 × 20 × 10 mm) **glued** to the chamfered face, just below the camera board (back of the board on the wall, buzzer facing inward). In the `.scad` it is only a mock-up for the clearance check (`mock_buzzer`), not a printed part.
- **Left wall**: 16x2 LCD (window on the bezel).
- **Right wall**: LED ring (16 slots aligned with the LEDs).
- **Open back**: the two rear walls (`x=A` and `y=B`) are missing, so USB-C and the electronics stack stay accessible.
- **Screwless lid**: rests on the rim and is located by an inner lip, with no snap fit.

Size: 115 × 115 × 72 mm (body) + 3 mm lid. Floor thickness 1.5 mm.

The lightweight floor (`lightweight_floor = true`) has three large openings, a 10 mm perimeter frame, cross ribs and solid areas under all pads and posts. Every mounting area is tied to the frame by a 6 mm wide rib; the body STL is a single component with manifold edges. Set `lightweight_floor = false` for a solid floor.

Geometric volume of the body: 49.45 cm³ (−39.4% compared with the open-back body with a solid 3 mm floor; data in `renders/lightweight_volume.json`). This is not a measure of print time or filament use: compare the STL files in the slicer with the same profile. Mechanical strength and physical fit have not been verified.

The lid is engraved with **larp.** (project name, Righteous font, 0.8 mm deep), customisable through the `logo_*` parameters in the `.scad` (text, size, depth, position). In renders the lettering is **blue** (`logo_color`, `#3d8bff`): `logo_inlay()` is the exact fill of the engraving, flush with the lid surface, and can be exported as a second colour (`part = "logo_inlay"` → `stl/smart_camera_logo_inlay.stl`, already oriented for printing).

## Files

| File | Description |
|------|-------------|
| `smart_camera_enclosure.scad` | Parametric source (`part = body / lid / lid_view / ring_retainer / clamp_usb / clamp_inner / fit / all`) |
| `stl/smart_camera_body.stl` | Body (print with the floor on the bed) |
| `stl/smart_camera_lid.stl` | Lid (already flipped for printing) |
| `stl/smart_camera_ring_retainer.stl` | Flange that holds the LED ring against the wall |
| `parts/grove_passive_buzzer.scad` | Parametric model of the Grove Passive Buzzer (SKU 107020109), with sources and estimates stated in the file |
| `stl/grove_passive_buzzer_mock.stl` | Buzzer mock-up (fit check only, not printed) |
| `stl/smart_camera_logo_inlay.stl` | Blue fill for the "larp" lettering (2nd colour, optional) |
| `smart_camera_explode.scad`, `video/` | Exploded-view animation (OpenSCAD → frames → video): see the "Video" section |
| `stl/smart_camera_clamp_usb.stl`, `stl/smart_camera_clamp_inner.stl` | Clamps that hold the UNO Q + Media Carrier stack |
| `fonts/` | Righteous font (OFL license) used for the "larp" lettering engraved on the lid |
| `previews/` | Check renders (`fit_*` = assembled with component mock-ups) |

## Fasteners (everything is screwed, pilot holes for self-tapping screws in PLA/PETG)

| Qty | Screw | Where |
|-----|-------|-------|
| 4 | M3 × 8 | UNO Q stack clamps onto the 4 posts rising from the floor |
| 4 | M3 × 8 | LED ring flange onto the 4 bosses of the right wall |
| 4 | M2.5 × 8 | LCD onto the 4 bosses of the left wall |
| 4 | M2 × 5 | Camera onto the 4 bosses of the front face |

The **buzzer has no screws**: it is glued (glue or double-sided tape) to the wall, below the camera.

Assembly notes:
- **Media Carrier: the datasheet shows no mounting holes** (it plugs into the UNO Q through JMEDIA/JMISC). The stack therefore rests on 4 floor pads (h 8 mm; the pins under the carrier protrude 5.97 mm) and is clamped from above by 2 clamps: their legs have a Ø2.7 pin that enters the 4 UNO Q holes (Ø3.2) and presses the stack onto the pads.
- **Carrier pads and connectors**: on the underside of the carrier (datasheet ASX00083 p.24) there are the CSI0/CSI1/DSI0 connectors (h 1.81 mm), the 3 audio jacks (h ~4.6 mm) and the two pass-through headers (h 5.97 mm). The pads under UNO Q holes 1 and 2 would land right on CSI0 and DSI0, so they were moved into the free strip on the USB side (`pad_pos`: u = 5 mm). The pads under holes 3 and 4 are clear. **CSI0 and CSI1 both remain usable** for the camera cable.
- **LED ring: no mounting holes.** It is centred by a small rim on the wall and pressed by a collar on the screwed flange (LED side toward the wall, light through the slots). The flange has notches for the Grove connector and the DIN/DOUT pads.
- Wall bosses have a teardrop section (45°), so the body prints without supports.

## Dimensions used (from datasheets)

- **Arduino UNO Q** (datasheet ABX00162/ABX00173, §12): 68.58 × 53.34 mm, 4 holes R1.6 at (13.97, 2.54), (15.24, 50.80), (66.04, 7.62), (66.04, 35.56); top components up to 8.5–9.1 mm; bottom parts < 2 mm.
- **UNO Media Carrier** (datasheet ASX00083, §7): 68.58 × 53.34 mm, no holes; pins underneath 5.97 mm, 3.5 mm audio jacks on the edge.
- **Grove 16x2 LCD** (Seeed drawing / JHD1804): PCB 80 × 40 mm, Ø2.5 holes on a 76 × 36 pattern (2 mm from the edges), bezel 71 × 24, viewing area 64.5 × 14.5, total depth 13.5 mm.
- **Grove RGB LED Ring 16** (Seeed product page): Ø58 mm, inner hole ~42 mm, 16 3535 LEDs on a ~Ø50 circle.
- **IMX219 8MP** (official Raspberry Pi Camera v2.1 drawing, RP-008149): 25 × 23.862 mm, Ø2.2 holes on a 21 × 12.5 pattern; the lens centre is 9.462 mm from the FFC connector edge and lies on the axis of the hole column 14.5 mm from the opposite edge (the other column is 12.4 mm lower). In the model the "top" edge is the connector edge.
- **Grove Passive Buzzer** (SKU 107020109): **20 × 20 × 10 mm** (Seeed wiki + Botland, Gotronic and Switch Science listings agree). PCB thickness (1.6 mm), can diameter (12 mm), can position and Grove connector footprint (6 × 8.8 × 4.4 mm) are **estimates**: Seeed does not publish a mechanical drawing.
- **Opening position**: the lens opening and mock-up are centred between the four mounting holes (`cam_aperture_y`), not at the lens position of the RPi drawing cited above. Check this on the camera module actually used.

## To check on the real parts before printing

- **`stack_gap` (6 mm)**: carrier ↔ UNO Q distance with the connectors mated. **Not in the datasheets** (neither Arduino nor Samtec found). An estimate from the drawings gives about 7.7 mm (2.7 mm insulator + 5 mm UNO Q connector), but it is unconfirmed. If the real value differs, regenerate the body and clamps: the posts, the clamp legs and the USB-C opening depend on it. With the wrong leg length the clamps do not clamp (lower stack) or do not reach the posts (higher stack).
- **Camera module**: the ASIN of the purchased module (B0CPM292WP) is the **Waveshare Pi5-IMX219-77** (25 × 24 mm, 4 holes), not the official RPi module. Hole spacing, lens height (assumed 5 mm; the wall has up to ~6 mm of margin) and FFC connector side are verified only against the RPi v2 drawing: check with calipers. The included cable is 22 → 15 pin, compatible with the carrier's 22-pin CSI connectors (pitch not stated in the datasheet).
- `ring_led_phase`: rotation of the slots relative to the ring LEDs. LED #0 position, inner hole (41.8 mm), LED radius (25 mm) and thicknesses are not dimensioned by Seeed: measure with calipers. LEDs and Grove connector are on opposite faces (LEDs toward the wall).
- Dimensions of the parts on the underside of the carrier (connectors, jacks): read from the raster drawing in the datasheet, accuracy ~±0.3 mm.
- **Buzzer**: position chosen by design (centred below the camera board, 2.5 mm gap: `buzzer_gap`, `buzzer_x`). Checked in CAD: no interference with camera, LCD, LED ring, flange, stack and clamps (clearance ≥ 0.6 mm). The walls are closed: with the can facing inward the sound is muffled. If needed, add an outlet hole in the chamfered wall (not done, to leave the printed part unchanged).
- The top edge of the LCD window (72 mm) is a horizontal bridge when printed: use 100% fan on bridges.

## Regenerating

```bash
OS=~/Downloads/OpenSCAD-2026.10.08-x86_64.AppImage
$OS -D 'part="fit"' -o previews/fit.png smart_camera_enclosure.scad
for p in body lid ring_retainer clamp_usb clamp_inner logo_inlay; do
  $OS --backend=manifold -D "part=\"$p\"" -o stl/smart_camera_$p.stl smart_camera_enclosure.scad
done
```

Print: 0.2 mm layers, 3 perimeters, 20–25% infill, no supports.

## Video (exploded view)

`smart_camera_explode.scad` animates the actual model along the real assembly axes, in a single movement (explode → hold → re-assemble). Full pipeline:

```bash
video/build_assets.sh               # compile the meshes from scratch (manifold backend) into video/stl/
video/render_frames.sh 30 4         # 4K frames with OpenSCAD (30 fps, 4 processes)
video/encode.sh                     # 4K -> 1080p H.264 (the downscale acts as anti-aliasing)
cd ../videos/smart-camera-explode && npx hyperframes render . -q high -o renders/video.mp4
```

Copy the colour scheme `video/hackdark.json` to `~/.config/OpenSCAD/color-schemes/render/`. The video labels (electronic components only) are positioned in `videos/smart-camera-explode/index.html`.
