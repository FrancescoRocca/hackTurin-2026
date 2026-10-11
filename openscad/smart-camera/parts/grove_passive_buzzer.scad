/*
  Seeed Grove - Passive Buzzer (SKU 107020109)  -  fit-check mock-up
  ---------------------------------------------------------------------------
  3-5 V, ~2700 Hz, > 80 dB, Grove 4-pin port.

  What is VERIFIED (Seeed wiki + retailer spec sheets: Botland, Gotronic,
  Switch Science, all agree):
      module envelope ........ 20 x 20 x 10 mm   (board + buzzer)
  What is ESTIMATED (no mechanical drawing published by Seeed - measure it
  with a caliper before relying on it):
      PCB thickness .......... 1.6 mm
      piezo can .............. d12 mm, centred on the Y axis, shifted to -X
      Grove connector ........ 4-pin 2.0 mm pitch socket, 6 x 8.8 x 4.4 mm,
                               flush with the +X edge of the board

  The module is glued (no screws), so mounting holes are not modelled.

  Local frame: origin = centre of the board's BOTTOM (glued) face,
               +Z = up through the board and the buzzer,  Z in [0, bz_h].
  ---------------------------------------------------------------------------
*/

bz_w       = 20;     // board size X  (verified)
bz_l       = 20;     // board size Y  (verified)
bz_h       = 10;     // total height, board bottom -> top of the buzzer (verified)
bz_pcb_t   = 1.6;    // PCB thickness (estimate)
bz_can_d   = 12;     // piezo can diameter (estimate)
bz_can_x   = -2.5;   // can centre along X (estimate)
bz_hole_d  = 1.6;    // sound hole on top of the can (estimate)
bz_conn    = [6, 8.8, 4.4];   // Grove socket X, Y, Z above the PCB (estimate)

module grove_passive_buzzer() {
    // PCB
    color("#f2f4f7")
        translate([-bz_w/2, -bz_l/2, 0]) cube([bz_w, bz_l, bz_pcb_t]);
    // piezo can: cylinder up to the full 10 mm height, with a small sound hole
    color("#15171c")
        difference() {
            translate([bz_can_x, 0, bz_pcb_t - 0.01])
                cylinder(d = bz_can_d, h = bz_h - bz_pcb_t + 0.01, $fn = 64);
            translate([bz_can_x, 0, bz_h - 1.2])
                cylinder(d = bz_hole_d, h = 2, $fn = 24);
        }
    // Grove 4-pin socket on the +X edge
    color("#e9e6dc")
        translate([bz_w/2 - bz_conn[0], -bz_conn[1]/2, bz_pcb_t - 0.01])
            cube([bz_conn[0], bz_conn[1], bz_conn[2] + 0.01]);
}

// stand-alone preview / export
grove_passive_buzzer();
