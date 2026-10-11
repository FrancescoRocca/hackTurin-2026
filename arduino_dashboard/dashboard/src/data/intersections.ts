import type { Intersection, VehicleClass } from "./types";

/**
 * The six nodes of the network, south to north along Corso Bolzano.
 *
 * The coordinates are not estimated: they are the nodes shared in OpenStreetMap
 * between Corso Bolzano and the street that crosses it (extracted with Overpass
 * on 2026-10-11, intersecting ways on shared nodes). `osmNode` is the id of that
 * node, so the position can be checked on OSM.
 */
export const INTERSECTIONS: Intersection[] = [
  {
    id: "LRP-01",
    name: "Corso Vittorio Emanuele\u00a0II",
    street: "Corso Bolzano",
    lat: 45.06815,
    lng: 7.66412,
    arms: 4,
    note: "Southern end of the corridor: the intersection that feeds ring-road traffic into the centre.",
    installedAt: "2026-09-14T09:20:00+02:00",
    osmNode: 305489321,
  },
  {
    id: "LRP-02",
    name: "Ponte Unione Europea",
    street: "Corso Bolzano × Corso Matteotti",
    lat: 45.06968,
    lng: 7.66516,
    arms: 4,
    note: "Crossing of the Dora Riparia: the only node where the corridor is a bridge.",
    installedAt: "2026-09-14T11:05:00+02:00",
    osmNode: 305489335,
  },
  {
    id: "LRP-03",
    name: "Via Severino Grattoni",
    street: "Corso Bolzano",
    lat: 45.07126,
    lng: 7.66655,
    arms: 3,
    note: "Three-arm intersection: the east branch is one-way towards the centre.",
    installedAt: "2026-09-21T10:40:00+02:00",
    osmNode: 299441779,
  },
  {
    id: "LRP-04",
    name: "Via Sebastiano Grandis",
    street: "Corso Bolzano",
    lat: 45.07203,
    lng: 7.66744,
    arms: 3,
    note: "Minor intersection serving the inner side streets of the neighbourhood.",
    installedAt: "2026-09-21T15:10:00+02:00",
    osmNode: 299441801,
  },
  {
    id: "LRP-05",
    name: "Via Fratelli Ruffini",
    street: "Corso Bolzano",
    lat: 45.07281,
    lng: 7.66798,
    arms: 4,
    note: "The node with the highest share of cyclists: this is where the corridor meets the Corso Bolzano bike lane.",
    installedAt: "2026-10-02T08:55:00+02:00",
    osmNode: 266129110,
  },
  {
    id: "LRP-06",
    name: "Piazza XVIII Dicembre",
    street: "Corso Bolzano × Corso San Martino",
    lat: 45.0736,
    lng: 7.66795,
    arms: 5,
    note: "Northern end, in front of Porta Susa: five arms, many surface lines.",
    installedAt: "2026-10-02T14:25:00+02:00",
    osmNode: 266129142,
  },
];

/** Route of the corridor, from the southernmost node to the northernmost. */
export const CORRIDOR: [number, number][] = INTERSECTIONS.map((n) => [n.lat, n.lng]);

/**
 * Traffic character of each node: peak-hour flow and class mix on a weekday.
 * This is project material, not measured data: the dashboard says in several
 * places that the demo counts are simulated.
 */
export interface NodeCharacter {
  /** Passes in the peak hour of a weekday. */
  peakHourFlow: number;
  /** Class mix during weekday daytime hours (sums to 1). */
  mix: Record<VehicleClass, number>;
  /** Average confidence reported by the classifier at this node. */
  confidence: number;
  /** Node that starts silent, for the demo. */
  startsOffline?: boolean;
}

export const CHARACTER: Record<string, NodeCharacter> = {
  "LRP-01": {
    peakHourFlow: 1620,
    mix: { car: 0.66, motorcycle: 0.08, bicycle: 0.1, pedestrian: 0.12 },
    confidence: 0.94,
  },
  "LRP-02": {
    peakHourFlow: 1140,
    mix: { car: 0.64, motorcycle: 0.1, bicycle: 0.12, pedestrian: 0.11 },
    confidence: 0.92,
  },
  "LRP-03": {
    peakHourFlow: 1330,
    mix: { car: 0.62, motorcycle: 0.09, bicycle: 0.2, pedestrian: 0.07 },
    confidence: 0.91,
  },
  "LRP-04": {
    peakHourFlow: 760,
    mix: { car: 0.55, motorcycle: 0.08, bicycle: 0.22, pedestrian: 0.13 },
    confidence: 0.89,
  },
  "LRP-05": {
    peakHourFlow: 1010,
    mix: { car: 0.48, motorcycle: 0.1, bicycle: 0.3, pedestrian: 0.1 },
    confidence: 0.9,
  },
  "LRP-06": {
    peakHourFlow: 1410,
    mix: { car: 0.58, motorcycle: 0.09, bicycle: 0.13, pedestrian: 0.14 },
    confidence: 0.93,
    startsOffline: true,
  },
};
