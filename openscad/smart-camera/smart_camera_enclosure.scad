/*
  Smart Camera Enclosure  (v3 - open back, chamfered-corner body)
  ---------------------------------------------------------------------------
  Plan view (Z up), pentagon = square box with the FRONT vertical corner cut:

        y=B  + . . . . . . . . . . . . .
             |                          |
   LCD  ---> |   UNO Q + Media Carrier  :  <- USB-C, open side x=A
   (x=0)     |        (back corner)     |
             |                          |
       y=c   \                          |
              \ CAMERA (chamfer face,   |
               \  upper part, points    |
                \  forward)             |
                 +----------------------+  y=0
                x=c      RING (wall y=0)  x=A

  Everything is held by screws:
    - Arduino UNO Q + UNO Media Carrier : stack rests on 4 floor pads and is
      clamped by 2 printed clamps (2x M3 each) whose legs have locating pins
      in the 4 UNO Q holes. (The Media Carrier has NO mounting holes.)
    - Sony IMX219 camera  : 4x M2 into bosses on the chamfer face
    - Grove 16x2 LCD      : 4x M2.5 into bosses on the left wall (window)
    - Grove RGB LED Ring  : printed retainer, 4x M3 into wall bosses
    - Lid                 : resting cover with locating lip, no screws
    - Grove Passive Buzzer: GLUED to the chamfer wall, just below the camera

  Datasheet sources (see README.md):
    UNO Q ABX00162/173 datasheet sec.12, UNO Media Carrier ASX00083 sec.7,
    Seeed Grove-16x2 LCD outline (JHD1804), Seeed Grove RGB LED Ring 16
    product drawing, Raspberry Pi Camera v2 (IMX219) form factor.
  ---------------------------------------------------------------------------
*/

/* ======================= Render selection ======================= */
part = "fit";   // [body, lid, lid_view, logo_inlay, ring_retainer, clamp_usb, clamp_inner, buzzer, fit, all]

/* ======================= Shell ======================= */
A        = 115;   // outer size along X (LCD wall -> open USB side)
B        = 115;   // outer size along Y (ring wall -> open back)
H        = 72;    // body height (floor bottom -> top rim)
c        = 28;    // chamfer leg (camera face outer width = c*sqrt2 ~ 39.6)
wall     = 2.5;   // [2:0.5:4]
floor_t  = 1.5;
corner_r = 4;     // outer vertical edge rounding
lightweight_floor = true; // false restores the solid floor
floor_frame = 10;         // solid perimeter width
floor_mount_margin = 5;   // solid material beyond each floor mount radius
floor_rib_w = 6;          // ties every mount footprint to the perimeter

/* ======================= Arduino stack ======================= */
// UNO Q (ABX00162): 68.58 x 53.34, holes R1.6 (d3.2)
uno_l = 68.58;  uno_w = 53.34;
// UNO Q hole positions (datasheet); the clamps use them, the floor pads use pad_pos below
uno_holes = [[13.97, 2.54], [15.24, 50.80], [66.04, 7.62], [66.04, 35.56]];
uno_t      = 1.6;
carrier_t  = 1.6;
stack_gap  = 6.0;   // carrier top -> UNO Q bottom (mated JMEDIA/JMISC), to be measured
pad_h      = 8;     // floor pads: carrier bottom pins stick out 5.97 mm
pad_d      = 5;
uno_top_h  = 9.1;   // tallest part on UNO Q top (pin headers)
usb_v      = 37.8;  // USB-C centre along the short edge (from datasheet drawing)
usb_gap    = 9.5;   // board edge -> inner wall (room for clamp posts + plug)
stack_cy   = 62.67; // board centre Y in the enclosure
clamp_clear= 10.8;  // UNO Q top surface -> clamp underside
clamp_t    = 3;
clamp_preload = 0.3;// legs press this much into the stack
post_d     = 7;
m3_pilot   = 2.6;   // M3 self-tapping pilot
m3_clear   = 3.4;

/* ======================= Camera (IMX219, RPi v2 form factor) ======================= */
cam_w      = 25;     cam_h = 23.862;
// Official RPi Camera v2.1 drawing (RP-008149): the FFC connector edge is the
// "top" edge here. Lens centre is 9.462 from that edge; the 4 holes (d2.2) are
// 2 and 14.5 mm from the OPPOSITE (far) edge, i.e. one hole column sits ~on the
// lens axis (+0.1) and the other 12.4 mm below it.
cam_hole_s = [2, 23];          // from left edge
cam_hole_t = [cam_h - 14.5, cam_h - 2];   // from top (connector) edge = [9.362, 21.862]
cam_lens_t = 9.462;            // lens centre from top (connector) edge
cam_boss_h = 3;      // lens (5 mm tall) ends ~0.5 mm behind the outer surface
cam_boss_d = 4.4;
cam_pilot  = 1.7;    // M2
cam_hole_d = 13;     // covers 8.5 mm square lens holder diagonal
cam_z      = 60;     // lens centre height (upper part of the face)
// Midpoint of the four mounting holes (lens opening is centred between them).
cam_aperture_y = cam_lens_t - (cam_hole_t[0] + cam_hole_t[1])/2;

/* ======================= Grove Passive Buzzer (glued) ======================= */
// Module model + sources: parts/grove_passive_buzzer.scad (20 x 20 x 10 mm).
// Glued flat (board back on the wall) on the chamfer face, centred under the
// camera board.  No screws, no change to the printed parts.
use <parts/grove_passive_buzzer.scad>
buzzer_size = [20, 20, 10];   // must match parts/grove_passive_buzzer.scad
buzzer_gap  = 2.5;            // camera board lower edge -> buzzer top edge
buzzer_x    = 0;              // offset along the chamfer face (0 = centred)

/* ======================= Grove 16x2 LCD ======================= */
lcd_w = 80;  lcd_h = 40;
lcd_holes  = [[2, 2], [78, 2], [2, 38], [78, 38]];   // 76 x 36, d2.5
lcd_bz     = [2.4, 40 - 28.41, 71, 24];             // bezel x, y(from bottom), w, h
lcd_win_cl = 0.6;    // clearance around the bezel
lcd_standoff = 6.5;  // wall inner face -> PCB front (LCD body is ~7.3 deep)
lcd_boss_d = 4.6;
lcd_pilot  = 2.1;    // M2.5
lcd_y0     = 31.5;   // PCB end nearest the chamfer (world Y)
lcd_zbot   = 12;     // PCB bottom edge height
lcd_j1     = [13, 0, 16, 13];  // Grove connector relief pocket (x, y, w, h)
lcd_back   = 13;     // total depth behind wall (PCB + COB blob)

/* ======================= Grove RGB LED Ring 16 ======================= */
ring_od    = 58;     // datasheet 58 (Seeed scaled photo: 57.7)
ring_id    = 41.8;   // inner hole (scaled photo)
ring_t     = 1.6;
led_h      = 1.6;    // WS2813 Mini 3535 height: LEDs face the wall
ring_rim_id= 58.8;   // locating rim inner diameter
ring_rim_w = 1.8;
ring_rim_h = led_h + ring_t;
ring_led_r = 25;     // LED circle radius (50 mm pitch circle)
ring_led_n = 16;
ring_led_phase = 0;  // deg, LED #0 aligned with the Grove connector direction
ring_slot  = [6.5, 5];   // light slot (tangential x radial)
ring_xr    = 66;     // ring centre X on wall y=0
ring_zc    = 40;     // ring centre height
ring_boss_r= 34.5;
ring_boss_a= [45, 135, 225, 315];
ring_boss_d= 7;
ring_boss_h= 6;      // wall -> retainer underside
ret_t      = 2.5;
ret_or     = 31.5;   // plate annulus outer radius (+ ears to the bosses)
ret_ir     = 27.0;
ret_collar = [27.8, 29.2];
ring_conn_a= 0;      // Grove connector direction (0 = +X, toward USB wall)
ring_conn_half = 16; // deg free around the connector

/* ======================= Lid ======================= */
lid_t    = 3;
lid_lip  = 3;
lid_gap  = 0.3;
lip_w    = 1.6;

/* ======================= Logo (engraved on the lid top) ======================= */
use <fonts/Righteous-Regular.ttf>      // OFL, bundled so it renders anywhere
logo_text  = "larp.";
logo_font  = "Righteous";
logo_size  = 22;          // letter height (mm)
logo_depth = 0.8;         // engraving depth into the 3 mm lid
logo_pos   = [64, 22];    // text centre on the lid (clear of vents)
logo_spacing = 1.05;
logo_color = "#3d8bff";   // blue "larp": inlay that fills the engraving (render colour / 2nd filament)

$fn = 72;

/* ======================= derived ======================= */
k   = 1/sqrt(2);
cm  = (c + wall*sqrt(2))/2;            // chamfer inner face mid point (x=y=cm)
X0  = A - wall - usb_gap;              // stack frame origin (u=0 edge)
Y0  = stack_cy + uno_w/2;
z_car    = floor_t + pad_h;
z_uno    = z_car + carrier_t + stack_gap;
z_unotop = z_uno + uno_t;
z_pb     = z_unotop + clamp_clear;     // clamp underside
// buzzer centre in the camera frame (local y): below the camera board's lower edge
buzzer_y = (cam_lens_t - cam_h) - buzzer_gap - buzzer_size[1]/2;

// Floor pads (stack frame u,v). Pads 3/4 sit under UNO Q holes 3/4. Pads 1/2
// would fall on the carrier's CSI0 / DSI0 FPC connectors (underside, datasheet
// ASX00083 p.24), so they are moved into the free strip u<9.5 at the USB end.
pad_pos = [[5, 3.0], [5, uno_w - 3.0], [66.04, 7.62], [66.04, 35.56]];

clamp_usb_posts   = [[-5, 2.54], [-5, 50.80]];
clamp_usb_legs    = [[13.97, 2.54], [15.24, 50.80]];
clamp_inner_posts = [[73, 7.62], [73, 35.56]];
clamp_inner_legs  = [[66.04, 7.62], [66.04, 35.56]];

/* ======================= frames ======================= */
// All wall frames: origin on INNER face, +X = viewer's right, +Y = up,
// +Z = outward (through the wall). Negative Z = inside the box.
module f_lcd()  multmatrix([[0,0,-1,wall],[-1,0,0,lcd_y0+lcd_w],[0,1,0,lcd_zbot],[0,0,0,1]]) children();
module f_ring() multmatrix([[1,0,0,ring_xr],[0,0,-1,wall],[0,1,0,ring_zc],[0,0,0,1]]) children();
module f_cam()  multmatrix([[k,0,-k,cm],[-k,0,-k,cm],[0,1,0,cam_z],[0,0,0,1]]) children();
// stack frame (u along board length, v along width), rotated 180 deg
module f_stack() translate([X0, Y0, 0]) rotate([0, 0, 180]) children();

/* ======================= helpers ======================= */
module plan_outer() {
    offset(r = corner_r) offset(delta = -corner_r)
        polygon([[c,0],[A,0],[A,B],[0,B],[0,c]]);
}
module plan_inner() offset(delta = -wall) plan_outer();

// A protected footprint alone can become an island inside a floor opening.
// Tie every footprint to the nearest X perimeter with a continuous rib.
module floor_mount_keepout(p, d) {
    x = X0 - p[0];
    y = Y0 - p[1];
    translate([x, y]) circle(r = d/2 + floor_mount_margin);
    hull() {
        translate([x, y]) circle(d = floor_rib_w);
        translate([x < A/2 ? floor_frame/2 : A - floor_frame/2, y])
            circle(d = floor_rib_w);
    }
}

// horizontal boss on a wall frame: teardrop section (45 deg underside),
// prints upright without support and keeps the wall below it free
module teardrop2d(d) hull() { circle(d = d); translate([0, -d/2*sqrt(2)]) square(0.01, center = true); }
module wall_boss(p, d, h) translate([p[0], p[1], -h]) linear_extrude(h + 0.01) teardrop2d(d);
module rslot(w, h, r) offset(r = r) offset(delta = -r) square([w, h], center = true);
module ring_sector(r1, r2, a0, a1) {
    polygon(concat([for (a = [a0:2:a1]) r2*[cos(a), sin(a)]],
                   [for (a = [a1:-2:a0]) r1*[cos(a), sin(a)]]));
}

/* ======================= BODY ======================= */
module body() {
    difference() {
        union() {
            difference() {
                linear_extrude(H) plan_outer();
                translate([0, 0, floor_t]) linear_extrude(H) plan_inner();
                // Open the two rear sides above the floor; retain the LCD,
                // camera and LED-ring walls and all floor-mounted supports.
                translate([A - wall, -1, floor_t]) cube([wall + 2, B + 2, H]);
                translate([-1, B - wall, floor_t]) cube([A + 2, wall + 2, H]);
                // The rounded rear corner extends inside both cut planes.
                translate([A - wall - corner_r, B - wall - corner_r, floor_t])
                    cube([wall + corner_r + 1, wall + corner_r + 1, H]);
            }
            body_addons();
        }
        body_cuts();
    }
}

module body_addons() {
    // --- stack floor pads (clear of the carrier's underside connectors) ---
    f_stack() for (p = pad_pos)
        translate([p[0], p[1], floor_t - 0.01]) cylinder(d = pad_d, h = pad_h + 0.01);
    // --- clamp posts ---
    f_stack() for (p = concat(clamp_usb_posts, clamp_inner_posts))
        translate([p[0], p[1], floor_t - 0.01]) cylinder(d = post_d, h = z_pb - floor_t + 0.01);
    // --- camera bosses ---
    f_cam() for (s = cam_hole_s) for (t = cam_hole_t)
        wall_boss([s - cam_w/2, cam_lens_t - t], cam_boss_d, cam_boss_h);
    // --- LCD bosses ---
    f_lcd() for (p = lcd_holes) wall_boss(p, lcd_boss_d, lcd_standoff);
    // --- LED ring: locating rim + retainer bosses ---
    f_ring() {
        translate([0, 0, -ring_rim_h])
            linear_extrude(ring_rim_h + 0.01)
                difference() {
                    circle(d = ring_rim_id + 2*ring_rim_w);
                    circle(d = ring_rim_id);
                    ring_sector(0, 50, ring_conn_a - ring_conn_half, ring_conn_a + ring_conn_half);
                }
        for (a = ring_boss_a)
            wall_boss(ring_boss_r*[cos(a), sin(a)], ring_boss_d, ring_boss_h);
    }
}

module body_cuts() {
    // Large floor openings avoid a slow, dense perforation pattern. Preserve
    // the perimeter, two cross ribs, and a solid footprint under every mount.
    if (lightweight_floor)
        translate([0, 0, -0.1]) linear_extrude(floor_t + 0.2)
            difference() {
                intersection() {
                    offset(delta = -floor_frame) plan_outer();
                    union() for (y = [15, 43, 73])
                        translate([floor_frame, y]) square([A - 2*floor_frame, 20]);
                }
                for (p = pad_pos) floor_mount_keepout(p, pad_d);
                for (p = concat(clamp_usb_posts, clamp_inner_posts))
                    floor_mount_keepout(p, post_d);
            }
    // --- stack: clamp post pilots ---
    f_stack() for (p = concat(clamp_usb_posts, clamp_inner_posts))
        translate([p[0], p[1], z_pb - 12]) cylinder(d = m3_pilot, h = 13);
    // --- camera: lens hole + countersink + pilots ---
    f_cam() {
        translate([0, cam_aperture_y, -0.5]) cylinder(d = cam_hole_d, h = wall + 1);
        translate([0, cam_aperture_y, wall - 1.2]) cylinder(d1 = cam_hole_d, d2 = cam_hole_d + 4, h = 1.21);
        for (s = cam_hole_s) for (t = cam_hole_t)
            translate([s - cam_w/2, cam_lens_t - t, -cam_boss_h - 0.1])
                cylinder(d = cam_pilot, h = cam_boss_h + 1.5);
    }
    // --- LCD: window, connector relief, pilots ---
    f_lcd() {
        translate([lcd_bz[0] - lcd_win_cl, lcd_bz[1] - lcd_win_cl, -0.5])
            cube([lcd_bz[2] + 2*lcd_win_cl, lcd_bz[3] + 2*lcd_win_cl, wall + 1]);
        // keep-out for the LCD body (trims boss teardrop tips)
        translate([lcd_bz[0] - 0.3, lcd_bz[1] - 0.3, -lcd_standoff - 0.1])
            cube([lcd_bz[2] + 0.6, lcd_bz[3] + 0.6, lcd_standoff + 0.2]);
        translate([lcd_j1[0], lcd_j1[1], -0.01]) cube([lcd_j1[2], lcd_j1[3], 1.2]);
        for (p = lcd_holes)
            translate([p[0], p[1], -lcd_standoff - 0.1]) cylinder(d = lcd_pilot, h = lcd_standoff + 1.5);
    }
    // --- LED ring: light slots + retainer pilots ---
    f_ring() {
        for (i = [0 : ring_led_n - 1]) {
            a = ring_led_phase + i*360/ring_led_n;
            rotate([0, 0, a]) translate([ring_led_r, 0, -0.5])
                linear_extrude(wall + 1) rotate(90) rslot(ring_slot[0], ring_slot[1], 1.2);
        }
        for (a = ring_boss_a)
            translate([ring_boss_r*cos(a), ring_boss_r*sin(a), -ring_boss_h - 0.1])
                cylinder(d = m3_pilot, h = ring_boss_h + 1.5);
    }
}

/* ======================= LID ======================= */
module lid() {
    difference() {
        union() {
            linear_extrude(lid_t) plan_outer();
            // locating lip
            translate([0, 0, -lid_lip]) linear_extrude(lid_lip + 0.01)
                difference() {
                    offset(delta = -lid_gap) plan_inner();
                    offset(delta = -lid_gap - lip_w) plan_inner();
                }
        }
        // vents above the board stack
        for (i = [0 : 6])
            translate([44 + i*8, 45, -1]) cube([3.5, 40, lid_t + 2]);
        // engraved project name (readable from above)
        translate([logo_pos[0], logo_pos[1], lid_t - logo_depth])
            linear_extrude(logo_depth + 0.01)
                text(logo_text, size = logo_size, font = logo_font,
                     halign = "center", valign = "center", spacing = logo_spacing);
    }
}

// Blue inlay: exact fill of the engraved "larp" (flush with the lid top). The lid
// STL is unchanged; print this as a 2nd colour, or just use it for renders.
module logo_text2d() text(logo_text, size = logo_size, font = logo_font,
                          halign = "center", valign = "center", spacing = logo_spacing);
module logo_inlay() color(logo_color)
    translate([logo_pos[0], logo_pos[1], lid_t - logo_depth])
        linear_extrude(logo_depth) logo_text2d();

/* ======================= LED RING RETAINER ======================= */
// modelled in the ring frame (wall at z=0, box at z<0)
module ring_retainer_local() {
    gaps = [[ring_conn_a, ring_conn_half], [90, 10], [270, 10]];   // connector, DIN/DOUT pads
    difference() {
        union() {
            // plate: annulus + ears to the screw bosses
            translate([0, 0, -ring_boss_h - ret_t]) linear_extrude(ret_t) {
                circle(r = ret_or);
                for (a = ring_boss_a) hull() {
                    translate(ring_boss_r*[cos(a), sin(a)]) circle(d = ring_boss_d);
                    rotate(a) translate([ret_or - 4, 0]) square([1, 12], center = true);
                }
            }
            // contact collar (presses the PCB edge onto the wall)
            translate([0, 0, -ring_boss_h - 0.01])
                linear_extrude(ring_boss_h - ring_rim_h + clamp_preload + 0.01)
                    difference() {
                        circle(r = ret_collar[1]);
                        circle(r = ret_collar[0]);
                        for (g = gaps) ring_sector(0, 50, g[0] - g[1], g[0] + g[1]);
                    }
        }
        translate([0, 0, -50]) cylinder(r = ret_ir, h = 100);
        // notch for the Grove connector + cable
        translate([0, 0, -50]) linear_extrude(100)
            ring_sector(0, 60, ring_conn_a - ring_conn_half, ring_conn_a + ring_conn_half);
        for (a = ring_boss_a)
            translate([ring_boss_r*cos(a), ring_boss_r*sin(a), -50]) cylinder(d = m3_clear, h = 100);
    }
}

/* ======================= STACK CLAMPS ======================= */
// modelled in the stack frame at their installed height
module clamp(posts, legs, cut_leg_u = 999) {
    difference() {
        union() {
            translate([0, 0, z_pb]) linear_extrude(clamp_t) {
                hull() for (p = posts) translate(p) circle(d = post_d);
                for (i = [0 : len(posts) - 1]) hull() {
                    translate(posts[i]) circle(d = 6);
                    translate(legs[i]) circle(d = 4.4);
                }
            }
            for (p = legs) intersection() {
                union() {
                    translate([p[0], p[1], z_unotop - clamp_preload])
                        cylinder(d = 4.4, h = z_pb - z_unotop + clamp_preload + 0.01);
                    // locating pin into the UNO Q hole (d3.2)
                    translate([p[0], p[1], z_unotop - clamp_preload - 1.2])
                        cylinder(d = 2.7, h = 1.21);
                }
                translate([-50, -50, 0]) cube([50 + cut_leg_u, 200, 200]);
            }
        }
        for (p = posts) translate([p[0], p[1], z_pb - 1]) cylinder(d = m3_clear, h = clamp_t + 2);
    }
}
module clamp_usb()   clamp(clamp_usb_posts, clamp_usb_legs, 16.9);   // keeps header pin 1 free
module clamp_inner() clamp(clamp_inner_posts, clamp_inner_legs);

/* ======================= MOCK-UPS (fit check only) ======================= */
module uno_outline() {
    // UNO Q / Media Carrier outline, points read from the datasheet drawing
    polygon([[0,0],[65.04,0],[66.04,0.98],[66.04,2.54],[uno_l,5.08],[uno_l,37.85],
             [66.04,40.39],[66.04,51.82],[64.51,uno_w],[0,uno_w]]);
}
module mock_stack() f_stack() {
    color("SteelBlue") translate([0, 0, z_car]) linear_extrude(carrier_t) uno_outline();
    // mated JMEDIA / JMISC connector blocks (UNO Q underside, 3.01 x 38.5)
    color("DimGray") translate([10.18, 7.43, z_car + carrier_t]) cube([3.01, 38.5, stack_gap]);
    color("DimGray") translate([57.04, 7.43, z_car + carrier_t]) cube([3.01, 38.5, stack_gap]);
    // --- Media Carrier UNDERSIDE parts (ASX00083 p.24, bottom view, X mirrored
    //     into the UNO Q frame; raster-measured, +-0.3 mm) ---
    color("DarkSlateGray") {
        translate([9.5, 7.6, z_car - 5.97])  cube([4.0, 38.1, 5.97]);    // JMISC/JMEDIA pass-through
        translate([56.1, 7.6, z_car - 5.97]) cube([4.9, 38.1, 5.97]);
        translate([10.0, 1.0, z_car - 1.81]) cube([15.6, 5.5, 1.81]);    // CSI0
        translate([26.6, 1.0, z_car - 1.81]) cube([15.6, 5.5, 1.81]);    // CSI1
        translate([10.0, 47.1, z_car - 1.81]) cube([15.6, 5.5, 1.81]);   // DSI0
        translate([45.7, 39.7, z_car - 4.6]) cube([7.4, 15.0, 4.6]);     // audio jack A1
        translate([30.5, 39.7, z_car - 4.6]) cube([7.4, 15.0, 4.6]);     // audio jack A2
        translate([45.7, -1.7, z_car - 4.6]) cube([7.4, 15.2, 4.6]);     // audio jack A3
    }
    color("Teal") translate([0, 0, z_uno]) linear_extrude(uno_t) uno_outline();
    color("Black") translate([17.3, 50.5, z_unotop]) cube([47.7, 2.6, 8.5]);
    color("Black") translate([26.5, 0.5, z_unotop]) cube([38.5, 2.6, 8.5]);
    color("Silver") translate([-0.5, usb_v - 4.5, z_unotop]) cube([7.9, 9, 3.0]);
}
module mock_camera() f_cam() {
    color("Orange") translate([-cam_w/2, cam_lens_t - cam_h, -cam_boss_h - 1]) cube([cam_w, cam_h, 1]);
    // Lens is drawn centred between the mounting holes, as in the cut-out.
    color("Black") translate([-4.25, cam_aperture_y - 4.25, -cam_boss_h]) cube([8.5, 8.5, 5]);
}
// board back glued on the wall, buzzer pointing into the box (-Z of the wall frame)
module mock_buzzer() f_cam() translate([buzzer_x, buzzer_y, 0]) rotate([180, 0, 0]) grove_passive_buzzer();
module mock_lcd() f_lcd() {
    color("Green") translate([0, 0, -lcd_standoff - 1.6]) cube([lcd_w, lcd_h, 1.6]);
    color("RoyalBlue") translate([lcd_bz[0], lcd_bz[1], -lcd_standoff]) cube([lcd_bz[2], lcd_bz[3], 7.3]);
}
module mock_ring() f_ring() color("Crimson")
    translate([0, 0, -ring_rim_h]) difference() {
        cylinder(d = ring_od, h = ring_t);
        translate([0, 0, -1]) cylinder(d = ring_id, h = ring_t + 2);
    }

module fit() {
    %body();
    mock_stack(); mock_camera(); mock_buzzer(); mock_lcd(); mock_ring();
    color("Gold") f_stack() { clamp_usb(); clamp_inner(); }
    color("Gold") f_ring() ring_retainer_local();
}

/* ======================= print orientations ======================= */
module ring_retainer_print() translate([0, 0, ring_boss_h + ret_t]) ring_retainer_local();
module clamp_print(which) {
    // plate on the bed, legs up
    translate([0, 0, z_pb + clamp_t]) mirror([0, 0, 1])
        if (which == "usb") clamp_usb(); else clamp_inner();
}
module lid_print() translate([0, 0, lid_t]) mirror([0, 0, 1]) lid();
module logo_inlay_print() translate([0, 0, lid_t]) mirror([0, 0, 1]) logo_inlay();

/* ======================= render ======================= */
if (part == "body")               body();
else if (part == "lid")           lid_print();
else if (part == "logo_inlay")    logo_inlay_print();
else if (part == "ring_retainer") ring_retainer_print();
else if (part == "clamp_usb")     clamp_print("usb");
else if (part == "clamp_inner")   clamp_print("inner");
else if (part == "buzzer")        grove_passive_buzzer();   // stand-alone module at the origin
else if (part == "none")          {}   // library mode (used by smart_camera_explode.scad)
else if (part == "fit")           fit();
else if (part == "lid_view")      { body(); translate([0, 0, H]) { lid(); logo_inlay(); } }   // closed box, as seen from above
else {
    body();
    translate([A + 15, 0, 0]) lid_print();
    translate([-50, 40, 0]) ring_retainer_print();
    translate([-30, 120, 0]) clamp_print("usb");
    translate([-110, 120, 0]) clamp_print("inner");
}
