import {
  VEHICLE_CLASSES,
  addCounts,
  emptyCounts,
  totalCounts,
  type AnomalyHour,
  type DetectionEvent,
  type HourBucket,
  type Intersection,
  type NodeSnapshot,
  type NodeStatus,
  type TrafficSource,
  type VehicleClass,
  type Verification,
  type VerifyRequest,
} from "./types";
import { CHARACTER, INTERSECTIONS } from "./intersections";

const HOUR = 3_600_000;

/**
 * Hourly profile of an urban arterial road: morning peak between 8 and 9,
 * a midday recovery, the main peak between 18 and 19, a drop at night.
 */
const WEEKDAY_PROFILE = [
  0.1, 0.06, 0.05, 0.05, 0.07, 0.14, 0.34, 0.78, 1.0, 0.82, 0.66, 0.64, 0.72, 0.74, 0.66, 0.7,
  0.82, 0.96, 1.0, 0.88, 0.66, 0.5, 0.34, 0.2,
];

/** Weekends have no commuting: lower peak, flatter day. */
const WEEKEND_PROFILE = [
  0.22, 0.16, 0.12, 0.08, 0.06, 0.08, 0.12, 0.2, 0.3, 0.44, 0.58, 0.66, 0.72, 0.74, 0.76, 0.78,
  0.8, 0.78, 0.7, 0.62, 0.54, 0.46, 0.4, 0.32,
];

function profileFor(hour: number, weekend: boolean): number {
  return (weekend ? WEEKEND_PROFILE : WEEKDAY_PROFILE)[hour];
}

function isWeekend(ts: number): boolean {
  const d = new Date(ts).getDay();
  return d === 0 || d === 6;
}

/** Deterministic PRNG: the same day always produces the same numbers. */
function mulberry32(seed: number): () => number {
  let a = seed >>> 0;
  return () => {
    a = (a + 0x6d2b79f5) >>> 0;
    let t = a;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

function hashString(s: string): number {
  let h = 2166136261;
  for (let i = 0; i < s.length; i++) {
    h ^= s.charCodeAt(i);
    h = Math.imul(h, 16777619);
  }
  return h >>> 0;
}

function dayKey(ts: number): string {
  const d = new Date(ts);
  const p = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}`;
}

function hourStart(ts: number): number {
  const d = new Date(ts);
  d.setMinutes(0, 0, 0);
  return d.getTime();
}

function mean(xs: number[]): number {
  return xs.reduce((a, b) => a + b, 0) / (xs.length || 1);
}

function stdev(xs: number[], m = mean(xs)): number {
  if (xs.length < 2) return 0;
  return Math.sqrt(xs.reduce((a, b) => a + (b - m) ** 2, 0) / (xs.length - 1));
}

/**
 * Class mix for one hour: at night pedestrians drop off and vehicles remain;
 * on weekends bicycles and pedestrians grow. This is not measured data, it is
 * a plausible shape for a Turin arterial road.
 */
function mixFor(nodeId: string, hour: number, weekend: boolean): Record<VehicleClass, number> {
  const base = CHARACTER[nodeId].mix;
  const nightFactor = hour >= 22 || hour <= 5 ? 0.25 : hour <= 6 || hour >= 21 ? 0.55 : 1;
  const weekendFactor = weekend ? 1.35 : 1;
  const raw: Record<VehicleClass, number> = {
    car: base.car * (nightFactor >= 1 ? 1 : 1.1),
    bicycle: base.bicycle * nightFactor * weekendFactor,
    motorcycle: base.motorcycle * (nightFactor < 1 ? nightFactor * 0.5 : 1) * (weekend ? 1.15 : 1),
    pedestrian: base.pedestrian * (hour >= 7 && hour <= 20 ? 1 : 0.35) * weekendFactor,
  };
  const sum = totalCounts(raw);
  const out = emptyCounts();
  for (const c of VEHICLE_CLASSES) out[c] = raw[c] / (sum || 1);
  return out;
}

/**
 * Hand-planted anomalies at daytime hours, so the comparison has statistical
 * weight. They give the verification flow something to verify, and they are
 * synthetic like everything else. Not every node gets one: two online nodes
 * stay clean so the demo shows a calm state next to a flagged one.
 */
function injectedMultiplier(
  nodeId: string,
  dayOffset: number,
  hour: number,
  cls: VehicleClass,
): number {
  if (dayOffset === 0) {
    if (nodeId === "LRP-01" && hour === 8 && cls === "bicycle") return 3.2;
    if (nodeId === "LRP-03" && hour === 7 && cls === "motorcycle") return 3.4;
    if (nodeId === "LRP-05" && hour === 10 && cls === "bicycle") return 2.6;
  }
  if (dayOffset === 1) {
    if (nodeId === "LRP-03" && hour === 19 && cls === "motorcycle") return 3.1;
  }
  return 1;
}

interface NodeRuntime {
  node: Intersection;
  /** Last known heartbeat. */
  lastBeat: number;
  /** When the node starts reporting again, if it is silent. null = reporting. */
  resumesAt: number | null;
  /** Since when it has been silent; null if reporting. */
  silentSince: number | null;
}

const VERIFY_KEY = "larp.verifications.v1";

function readVerifications(): Verification[] {
  if (typeof localStorage === "undefined") return [];
  try {
    const raw = localStorage.getItem(VERIFY_KEY);
    return raw ? (JSON.parse(raw) as Verification[]) : [];
  } catch {
    return [];
  }
}

function writeVerifications(all: Verification[]): void {
  if (typeof localStorage === "undefined") return;
  try {
    localStorage.setItem(VERIFY_KEY, JSON.stringify(all));
  } catch {
    /* storage full or denied: the verification stays in memory for the session */
  }
}

/**
 * Synthetic source. Deterministic per node and day: reloading the page does
 * not change the history, only the present keeps flowing.
 */
export class SimulatedSource implements TrafficSource {
  readonly kind = "simulated" as const;
  readonly synthetic = true;

  private readonly startedAt: number;
  private readonly runtimes: NodeRuntime[];
  private verifications: Verification[];
  private readonly liveEvents = new Map<string, DetectionEvent[]>();
  /** Fractional remainder of passes not yet emitted, per node. */
  private readonly pendingDraw = new Map<string, number>();
  private lastTick = 0;
  private timer: number | null = null;
  private subscribers = new Set<(e: DetectionEvent) => void>();
  private seq = 0;

  constructor(private readonly now: () => number = () => Date.now()) {
    this.startedAt = this.now();
    this.verifications = readVerifications();
    this.runtimes = INTERSECTIONS.map((node) => {
      const offline = CHARACTER[node.id].startsOffline === true;
      return {
        node,
        lastBeat: offline ? this.startedAt - 41 * 60_000 : this.startedAt,
        resumesAt: offline ? this.startedAt + 90_000 : null,
        silentSince: offline ? this.startedAt - 41 * 60_000 : null,
      };
    });
  }

  async listNodes(): Promise<Intersection[]> {
    return INTERSECTIONS;
  }

  private runtime(nodeId: string): NodeRuntime {
    const r = this.runtimes.find((x) => x.node.id === nodeId);
    if (!r) throw new Error(`unknown node: ${nodeId}`);
    return r;
  }

  /**
   * A node is online if it was never silenced, or if it has already resumed.
   * The silence stays recorded: the gap in the hourly field is not erased
   * when the node starts reporting again.
   */
  private isOnline(r: NodeRuntime, at: number): boolean {
    return r.resumesAt === null || at >= r.resumesAt;
  }

  statuses(): NodeStatus[] {
    const at = this.now();
    return this.runtimes.map((r) => {
      const online = this.isOnline(r, at);
      if (online) r.lastBeat = at;
      const ch = CHARACTER[r.node.id];
      return {
        nodeId: r.node.id,
        online,
        lastBeat: r.lastBeat,
        firmware: "0.4.2",
        uptimeMs: at - new Date(r.node.installedAt).getTime(),
        confidenceAvg: ch.confidence,
      };
    });
  }

  /** Hourly buckets for the last `hours` hours, oldest first. */
  private history(nodeId: string, hours: number, at: number): HourBucket[] {
    const r = this.runtime(nodeId);
    const ch = CHARACTER[nodeId];
    const last = hourStart(at);
    const out: HourBucket[] = [];
    for (let i = hours - 1; i >= 0; i--) {
      const ts = last - i * HOUR;
      const d = new Date(ts);
      const weekend = isWeekend(ts);
      const dayOffset = Math.round(
        (hourStart(this.startedAt) - hourStart(ts)) / (24 * HOUR),
      );
      const rng = mulberry32(hashString(`${nodeId}|${dayKey(ts)}|${d.getHours()}`));
      const expected = ch.peakHourFlow * profileFor(d.getHours(), weekend);
      const gap =
        r.silentSince !== null &&
        ts >= hourStart(r.silentSince) &&
        ts <= (r.resumesAt === null ? Number.POSITIVE_INFINITY : hourStart(r.resumesAt));
      const counts = emptyCounts();
      if (!gap) {
        const mix = mixFor(nodeId, d.getHours(), weekend);
        const jitter = 0.82 + rng() * 0.36;
        const total = expected * jitter;
        for (const c of VEHICLE_CLASSES) {
          const inj = injectedMultiplier(nodeId, dayOffset, d.getHours(), c);
          counts[c] = Math.max(0, Math.round(total * mix[c] * inj * (0.85 + rng() * 0.3)));
        }
      }
      out.push(gap ? { ts, counts, missing: true } : { ts, counts });
    }
    // The current hour is not over yet: the baseline covers only the elapsed part.
    const lastFull = out[out.length - 1];
    if (lastFull && !lastFull.missing) {
      const elapsed = Math.min(1, Math.max(0, (at - lastFull.ts) / HOUR));
      const scaled = emptyCounts();
      for (const c of VEHICLE_CLASSES) scaled[c] = Math.round(lastFull.counts[c] * elapsed);
      out[out.length - 1] = { ts: lastFull.ts, counts: scaled };
    }
    return out;
  }

  private anomalies(nodeId: string, at: number): AnomalyHour[] {
    // Baseline over 28 days: when grouping weekdays and weekends, a seven-day
    // window would leave only two samples for each weekend hour.
    const hours = this.history(nodeId, 28 * 24, at);
    const buckets = new Map<string, number[]>();
    for (const h of hours) {
      const d = new Date(h.ts);
      const key = `${isWeekend(h.ts) ? "w" : "f"}:${d.getHours()}`;
      for (const c of VEHICLE_CLASSES) {
        const arr = buckets.get(`${key}:${c}`) ?? [];
        arr.push(h.counts[c]);
        buckets.set(`${key}:${c}`, arr);
      }
    }
    const recent = hours.slice(-25, -1);
    const found: AnomalyHour[] = [];
    for (const h of recent) {
      if (h.missing) continue;
      const d = new Date(h.ts);
      const key = `${isWeekend(h.ts) ? "w" : "f"}:${d.getHours()}`;
      for (const c of VEHICLE_CLASSES) {
        const series = buckets.get(`${key}:${c}`)?.slice(0, -1) ?? [];
        if (series.length < 3) continue;
        const m = mean(series);
        const sd = stdev(series, m);
        const observed = h.counts[c];
        if (sd < 1.5 || m < 8) continue;
        const z = (observed - m) / sd;
        // A spike must have substance; a drop is flagged even on low numbers.
        if (z > 0 && observed < 12) continue;
        if (Math.abs(z) >= 4) {
          found.push({ ts: h.ts, cls: c, observed, expected: Math.round(m), z });
        }
      }
    }
    return found.sort((a, b) => Math.abs(b.z) - Math.abs(a.z)).slice(0, 3);
  }

  async snapshot(nodeId: string): Promise<NodeSnapshot> {
    const at = this.now();
    const r = this.runtime(nodeId);
    this.isOnline(r, at);
    const hourly = this.history(nodeId, 24, at);
    const previous = this.history(nodeId, 48, at).slice(0, 24);
    const status = this.statuses().find((s) => s.nodeId === nodeId)!;

    const today = hourly.reduce((acc, h) => addCounts(acc, h.counts), emptyCounts());
    const yesterday = previous.reduce((acc, h) => addCounts(acc, h.counts), emptyCounts());

    let peakHour: number | null = null;
    let peakHourTotal = 0;
    hourly.forEach((h) => {
      if (h.missing) return;
      const t = totalCounts(h.counts);
      if (t > peakHourTotal) {
        peakHourTotal = t;
        peakHour = new Date(h.ts).getHours();
      }
    });

    const events = this.liveEvents.get(nodeId) ?? [];
    const currentRate = events.filter((e) => at - e.ts <= 60_000).length;

    return {
      node: r.node,
      status,
      hourly,
      today,
      yesterday,
      todayTotal: totalCounts(today),
      yesterdayTotal: totalCounts(yesterday),
      peakHour: status.online ? peakHour : null,
      peakHourTotal: status.online ? peakHourTotal : 0,
      currentRate,
      events,
      anomalies: status.online ? this.anomalies(nodeId, at) : [],
      verifications: this.verifications.filter((v) => v.key.startsWith(`${nodeId}:`)),
    };
  }

  async verify(req: VerifyRequest): Promise<Verification> {
    const record: Verification = {
      key: req.key,
      verdict: req.verdict,
      note: req.note,
      operator: req.operator,
      at: this.now(),
    };
    this.verifications = [...this.verifications.filter((v) => v.key !== req.key), record];
    writeVerifications(this.verifications);
    return record;
  }

  stream(handler: (e: DetectionEvent) => void): () => void {
    this.subscribers.add(handler);
    if (this.timer === null) {
      this.timer = setInterval(() => this.tick(), 1100) as unknown as number;
    }
    return () => {
      this.subscribers.delete(handler);
      if (this.subscribers.size === 0 && this.timer !== null) {
        clearInterval(this.timer);
        this.timer = null;
      }
    };
  }

  /** One simulation beat: a few passes for each online node. */
  private tick(): void {
    const at = this.now();
    const previous = this.lastTick || at - 1100;
    this.lastTick = at;
    const elapsed = Math.min(6, Math.max(0.2, (at - previous) / 1000));

    for (const r of this.runtimes) {
      if (!this.isOnline(r, at)) continue;
      const ch = CHARACTER[r.node.id];
      const hour = new Date(at).getHours();
      const ratePerSec = (ch.peakHourFlow * profileFor(hour, isWeekend(at))) / 3600;
      const rng = mulberry32(hashString(`${r.node.id}|${Math.floor(at / 1000)}|${this.seq}`));
      // The fractional remainder is not discarded: it carries over to the next
      // beat, otherwise medium-flow nodes would never emit a pass.
      const jitter = 0.6 + rng() * 0.8;
      const accrued = (this.pendingDraw.get(r.node.id) ?? 0) + ratePerSec * elapsed * jitter;
      const n = Math.min(9, Math.floor(accrued));
      this.pendingDraw.set(r.node.id, accrued - n);
      if (n <= 0) continue;

      const mix = mixFor(r.node.id, hour, isWeekend(at));
      const list = this.liveEvents.get(r.node.id) ?? [];
      for (let i = 0; i < n; i++) {
        const roll = rng();
        let acc = 0;
        let cls: VehicleClass = "car";
        for (const c of VEHICLE_CLASSES) {
          acc += mix[c];
          if (roll <= acc) {
            cls = c;
            break;
          }
        }
        const confidence = Math.min(
          0.995,
          Math.max(0.6, ch.confidence + (rng() - 0.5) * 0.08 * (cls === "motorcycle" ? 1.5 : 1)),
        );
        const event: DetectionEvent = {
          id: `${r.node.id}-${at}-${this.seq++}`,
          nodeId: r.node.id,
          ts: at,
          cls,
          confidence: Math.round(confidence * 100) / 100,
          approach: rng() > 0.5 ? "north" : "south",
        };
        list.unshift(event);
        this.subscribers.forEach((h) => h(event));
      }
      this.liveEvents.set(r.node.id, list.slice(0, 80));
    }
  }
}
