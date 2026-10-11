/**
 * Data model of the larp network.
 *
 * The device classifies on board and transmits **only** counts and metadata:
 * nothing in this model can carry an image. If frames are ever transmitted,
 * they enter here as a new field and a deliberate product decision, never as an
 * implicit assumption.
 */

/**
 * Taxonomy detected on board. Order is presentation order.
 *
 * These are exactly the four classes the node counts
 * (`larp_crosswalk/python/object_tracker.py`, `CLASSES`):
 *   car → car · bicycle/bike → bicycle · motorcycle/motorbike → motorcycle ·
 *   person → pedestrian.
 * Every other model label (truck, bus…) is discarded by the device, so it
 * does not exist here.
 */
export const VEHICLE_CLASSES = ["car", "bicycle", "motorcycle", "pedestrian"] as const;

export type VehicleClass = (typeof VEHICLE_CLASSES)[number];

export const CLASS_LABEL: Record<VehicleClass, string> = {
  car: "car",
  bicycle: "bicycle",
  motorcycle: "motorcycle",
  pedestrian: "pedestrian",
};

export type Counts = Record<VehicleClass, number>;

/** A monitored intersection, anchored to a real OpenStreetMap node. */
export interface Intersection {
  /** Node identifier, printed on the enclosure. */
  id: string;
  /** Intersection name as an operator reads it. */
  name: string;
  /** Street that hosts the node. */
  street: string;
  lat: number;
  lng: number;
  /** Number of arms of the intersection. */
  arms: number;
  /** Why this node sits where it does. */
  note: string;
  /** Commissioning time, ISO. */
  installedAt: string;
  /** Reference of the shared OSM node the position was taken from. */
  osmNode: number;
}

export type Approach = "north" | "south";

/** A single classified pass. No frame, no reference to images. */
export interface DetectionEvent {
  id: string;
  nodeId: string;
  /** Epoch ms. */
  ts: number;
  cls: VehicleClass;
  /** Confidence reported by the on-board classifier, 0..1. */
  confidence: number;
  approach: Approach;
}

/** Counts aggregated over one calendar hour. */
export interface HourBucket {
  /** Epoch ms of the start of the hour. */
  ts: number;
  counts: Counts;
  /**
   * True when nothing arrived for that hour: the node was silent.
   * It is a declared absence, not a count of zero.
   */
  missing?: boolean;
}

/** Device state. */
export interface NodeStatus {
  nodeId: string;
  online: boolean;
  /** Epoch ms of the last heartbeat. */
  lastBeat: number;
  firmware: string;
  /** How long the node has been in service, ms. */
  uptimeMs: number;
  /** Average confidence reported by the classifier. */
  confidenceAvg: number;
}

/** An hour whose count departs from the node's own historical baseline. */
export interface AnomalyHour {
  ts: number;
  cls: VehicleClass;
  observed: number;
  /** Expected for that hour and class over the previous 7 days. */
  expected: number;
  /** Deviation in standard deviations. */
  z: number;
}

export type Verdict = "confirmed" | "sensor_error";

/** An operator's verdict on a count. */
export interface Verification {
  /** Key of the verified item. */
  key: string;
  verdict: Verdict;
  note: string;
  operator: string;
  /** Epoch ms of the verdict. */
  at: number;
}

/** Everything the dashboard shows for a node, in a single read. */
export interface NodeSnapshot {
  node: Intersection;
  status: NodeStatus;
  /** Counts for the last 24 hours, hour by hour (24 entries, oldest first). */
  hourly: HourBucket[];
  /** Totals per class over the last 24 hours. */
  today: Counts;
  /** Totals per class over the previous 24 hours, for comparison. */
  yesterday: Counts;
  /** Total passes over the last 24 hours. */
  todayTotal: number;
  yesterdayTotal: number;
  /** Peak hour of the day, 0..23, or null if the node is silent. */
  peakHour: number | null;
  peakHourTotal: number;
  /** Passes in the current hour. */
  currentRate: number;
  /** Latest events received, most recent first. */
  events: DetectionEvent[];
  /** Hours that depart from the historical baseline. */
  anomalies: AnomalyHour[];
  /** Verdicts already recorded for this node. */
  verifications: Verification[];
}

export interface VerifyRequest {
  key: string;
  nodeId: string;
  verdict: Verdict;
  note: string;
  operator: string;
}

/**
 * The seam between dashboard and data: one interface, two implementations.
 * `SimulatedSource` fills it with deterministic synthetic data;
 * `createHttpSource` documents the shape a real feed must have.
 */
export interface TrafficSource {
  readonly kind: "simulated" | "http";
  /** Synthetic data: the dashboard must say so, not hide it. */
  readonly synthetic: boolean;
  listNodes(): Promise<Intersection[]>;
  snapshot(nodeId: string): Promise<NodeSnapshot>;
  verify(req: VerifyRequest): Promise<Verification>;
  /** New passes in real time. Returns the unsubscribe function. */
  stream(handler: (e: DetectionEvent) => void): () => void;
}

export function emptyCounts(): Counts {
  return { car: 0, bicycle: 0, motorcycle: 0, pedestrian: 0 };
}

export function addCounts(a: Counts, b: Counts): Counts {
  const out = emptyCounts();
  for (const c of VEHICLE_CLASSES) out[c] = a[c] + b[c];
  return out;
}

export function totalCounts(c: Counts): number {
  let n = 0;
  for (const k of VEHICLE_CLASSES) n += c[k];
  return n;
}
