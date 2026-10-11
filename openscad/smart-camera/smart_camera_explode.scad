/*
  Smart Camera - exploded-view animation (hackTurin 2026)
  ---------------------------------------------------------------------------
  Drives the REAL parametric model (smart_camera_enclosure.scad) through an
  assembly / explode / re-assemble timeline.  One frame is selected with
      -D ft=<0..1>          (normalised time; 0 -> closed box, 1 -> end)
  or with OpenSCAD's own animation variable $t (File > Animate).

  Render one frame:
      openscad --projection=o --colorscheme=HackDark --imgsize=1920,1080 \
        -D ft=0.45 -o frame.png smart_camera_explode.scad
  Render the whole clip: see video/render_frames.sh

  Every exploded part moves along its REAL assembly axis:
    lid ............ +Z          (rests on the rim)
    clamps+screws .. +Z          (M3, from the top)
    UNO Q, carrier . +Z          (stack lifts off the floor pads)
    LED ring ....... +Y          (wall y=0, parts enter from the inside)
    LCD ............ +X          (wall x=0)
    camera ......... +(X,Y)/sqrt2 (chamfer face)
    buzzer ......... +(X,Y)/sqrt2 (glued under the camera, same face)
  All parts move TOGETHER in one single eased movement (explode, hold, re-assemble).
  ---------------------------------------------------------------------------
*/
include <smart_camera_enclosure.scad>
part = "none";           // library mode: do not draw anything from the include

/* ======================= mesh cache =======================
   The heavy CSG parts (body, lid, retainer, clamps) are compiled ONCE with the
   manifold backend into video/stl/*.stl (see video/build_assets.sh) and then
   imported per frame: preview-mode OpenCSG on the raw CSG shows z-fighting on
   the thin open walls, and re-evaluating it 700 times would be slow.
   asm = "" -> animation scene, otherwise export that single part (world coords). */
asm = "";
use_mesh = true;
stl_dir  = "video/stl/";

/* ======================= timeline ======================= */
T  = 21;                 // seconds of the clip
ft = -1;                 // override with -D ft=...   (-1 -> use $t)
tt = (ft >= 0 ? ft : $t) * T;

function cl(x)  = min(1, max(0, x));
function ez(x)  = let(u = cl(x)) u < 0.5 ? 4*u*u*u : 1 - pow(-2*u + 2, 3)/2;   // easeInOutCubic
// 0 = assembled, 1 = fully exploded.  out window (a,b), re-assembly window (c,d)
function pr(a, b, c, d) = ez((tt - a)/(b - a)) - ez((tt - c)/(d - c));

// ONE movement for every part: explode 2.0 -> 5.4 s, hold, re-assemble 12.8 -> 16.0 s
p_all     = pr( 2.0,  5.4, 12.8, 16.0);
p_lid     = p_all;   p_clscr  = p_all;   p_clamps = p_all;   p_uno    = p_all;
p_carrier = p_all;   p_rngscr = p_all;   p_ret    = p_all;   p_ring   = p_all;
p_lcdscr  = p_all;   p_lcd    = p_all;   p_camscr = p_all;   p_cam    = p_all;
p_buzzer  = p_all;

// overall "explosion" 0..1 (drives camera framing and orbit)
P_all = p_all;

/* ======================= explode distances (mm) ======================= */
d_lid    = 140;
d_clscr  = 146;
d_clamps = 128;
d_uno    = 106;
d_carr   = 82;
d_rngscr = 40;
d_ret    = 20;
d_ring   = 12;
d_lcdscr = 44;
d_lcd    = 22;
d_camscr = 38;
d_cam    = 19;
d_buz    = 38;     // buzzer: along the chamfer normal, far enough to be seen past the LCD and ring

/* ======================= camera ======================= */
rz_front = 20;
rz_back_a = 160;               // absolute azimuth of the "open back" exploded view
// gentle settle at the start / drift away at the end (closed-box hero shots)
rz_drift = -16 * (1 - ez(tt/2.4)) + 12 * ez((tt - 16.0)/5.0);
rz  = rz_front + (rz_back_a - rz_front) * P_all + rz_drift;
rx  = 62 + 8 * P_all;     // slightly lower camera on the closed hero shot
vpt_closed   = [52, 52, 38];  vpt_open = [56, 54, 104];
// framing follows the lid (the highest part): zoom out as it lifts, back in only as it lands
P_zoom = p_all;
$vpt = vpt_closed + (vpt_open - vpt_closed) * P_zoom;
$vpr = [rx, 0, rz];
vpd_closed = 440; vpd_open = 730;
$vpd = vpd_closed + (vpd_open - vpd_closed) * P_zoom;   // orthographic zoom (smaller = closer)

/* ======================= palette ======================= */
c_body   = "#d7dce4";
c_lid    = "#eceff4";
c_print  = "#ffb703";      // printed accessories
c_screw  = "#aeb6c4";
c_ringpc = "#3b4568";

/* ======================= helpers ======================= */
module screw(d, len, hd, hh) {          // axis along -Z, head on top
    color(c_screw) {
        cylinder(d = hd, h = hh, $fn = 24);
        translate([0, 0, -len]) cylinder(d = d, h = len + 0.01, $fn = 16);
    }
}

function hsv(h, s = 0.85, v = 1) =
    let(i = floor(h*6) % 6, f = h*6 - floor(h*6),
        p = v*(1 - s), q = v*(1 - f*s), t2 = v*(1 - (1 - f)*s))
    i == 0 ? [v, t2, p] : i == 1 ? [q, v, p] : i == 2 ? [p, v, t2] :
    i == 3 ? [p, q, v] : i == 4 ? [t2, p, v] : [v, p, q];

/* ======================= split mock-ups ======================= */
module carrier_mock() f_stack() {
    color("#2f6fb3") translate([0, 0, z_car]) linear_extrude(carrier_t) uno_outline();
    color("#3b3f48") {
        translate([9.5, 7.6, z_car - 5.97])  cube([4.0, 38.1, 5.97]);
        translate([56.1, 7.6, z_car - 5.97]) cube([4.9, 38.1, 5.97]);
        translate([10.0, 1.0, z_car - 1.81]) cube([15.6, 5.5, 1.81]);
        translate([26.6, 1.0, z_car - 1.81]) cube([15.6, 5.5, 1.81]);
        translate([10.0, 47.1, z_car - 1.81]) cube([15.6, 5.5, 1.81]);
        translate([45.7, 39.7, z_car - 4.6]) cube([7.4, 15.0, 4.6]);
        translate([30.5, 39.7, z_car - 4.6]) cube([7.4, 15.0, 4.6]);
        translate([45.7, -1.7, z_car - 4.6]) cube([7.4, 15.2, 4.6]);
    }
}
module uno_mock() f_stack() {
    color("#222831") translate([10.18, 7.43, z_car + carrier_t]) cube([3.01, 38.5, stack_gap]);
    color("#222831") translate([57.04, 7.43, z_car + carrier_t]) cube([3.01, 38.5, stack_gap]);
    color("#0e9aa7") translate([0, 0, z_uno]) linear_extrude(uno_t) uno_outline();
    color("#14181f") translate([17.3, 50.5, z_unotop]) cube([47.7, 2.6, 8.5]);
    color("#14181f") translate([26.5, 0.5, z_unotop]) cube([38.5, 2.6, 8.5]);
    color("#d0d4db") translate([-0.5, usb_v - 4.5, z_unotop]) cube([7.9, 9, 3.0]);
}
module ring_mock(phase = 0) f_ring() {
    color(c_ringpc) translate([0, 0, -ring_rim_h]) difference() {
        cylinder(d = ring_od, h = ring_t, $fn = 96);
        translate([0, 0, -1]) cylinder(d = ring_id, h = ring_t + 2, $fn = 96);
    }
    // 16 WS2813 LEDs on the wall-facing side, animated rainbow chase
    for (i = [0 : ring_led_n - 1])
        color(hsv(((i/ring_led_n) + phase) % 1)) rotate([0, 0, ring_led_phase + i*360/ring_led_n])
            translate([ring_led_r - 1.75, -1.75, -led_h]) cube([3.5, 3.5, led_h]);
}

/* ======================= screws, per group ======================= */
module clamp_screws() f_stack()
    for (p = concat(clamp_usb_posts, clamp_inner_posts))
        translate([p[0], p[1], z_pb + clamp_t]) screw(3, 8, 5.6, 2);
module ring_screws() f_ring()
    for (a = ring_boss_a)
        translate([ring_boss_r*cos(a), ring_boss_r*sin(a), -(ring_boss_h + ret_t)])
            rotate([180, 0, 0]) screw(3, 8, 5.6, 2);
module lcd_screws() f_lcd()
    for (p = lcd_holes)
        translate([p[0], p[1], -lcd_standoff - 1.6]) rotate([180, 0, 0]) screw(2.5, 8, 4.6, 1.8);
module cam_screws() f_cam()
    for (s = cam_hole_s) for (t = cam_hole_t)
        translate([s - cam_w/2, cam_lens_t - t, -cam_boss_h - 1]) rotate([180, 0, 0]) screw(2, 5, 3.8, 1.4);

/* ======================= scene ======================= */
module m_body()      { if (use_mesh) import(str(stl_dir, "body_asm.stl"));      else body(); }
module m_lid()       { if (use_mesh) import(str(stl_dir, "lid_asm.stl"));       else lid(); }
module m_retainer()  { if (use_mesh) import(str(stl_dir, "retainer_asm.stl"));  else f_ring() ring_retainer_local(); }
module m_clamp_usb() { if (use_mesh) import(str(stl_dir, "clamp_usb_asm.stl")); else f_stack() clamp_usb(); }
module m_clamp_in()  { if (use_mesh) import(str(stl_dir, "clamp_inner_asm.stl")); else f_stack() clamp_inner(); }

module scene() {
    color(c_body) m_body();

    translate([0, 0, d_lid * p_lid]) translate([0, 0, H]) { color(c_lid) m_lid(); logo_inlay(); }

    translate([0, 0, d_clscr * p_clscr])  clamp_screws();
    translate([0, 0, d_clamps * p_clamps]) color(c_print) { m_clamp_usb(); m_clamp_in(); }
    translate([0, 0, d_uno * p_uno])       uno_mock();
    translate([0, 0, d_carr * p_carrier])  carrier_mock();

    // LED ring: +Y (inside the box)
    translate([0, d_rngscr * p_rngscr, 0]) ring_screws();
    translate([0, d_ret * p_ret, 0]) color(c_print) m_retainer();
    translate([0, d_ring * p_ring, 0]) ring_mock(phase = tt * 0.25);

    // LCD: +X
    translate([d_lcdscr * p_lcdscr, 0, 0]) lcd_screws();
    translate([d_lcd * p_lcd, 0, 0]) mock_lcd();

    // buzzer: glued under the camera, comes off along the chamfer normal
    translate([k * d_buz * p_buzzer, k * d_buz * p_buzzer, 0]) mock_buzzer();

    // camera: diagonal
    translate([k * d_camscr * p_camscr, k * d_camscr * p_camscr, 0]) cam_screws();
    translate([k * d_cam * p_cam, k * d_cam * p_cam, 0]) mock_camera();
}

if      (asm == "body")         body();
else if (asm == "lid")          lid();
else if (asm == "retainer")     f_ring() ring_retainer_local();
else if (asm == "clamp_usb")    f_stack() clamp_usb();
else if (asm == "clamp_inner")  f_stack() clamp_inner();
else if (asm == "none")         {}   // library mode (interference tests)
else                            scene();
