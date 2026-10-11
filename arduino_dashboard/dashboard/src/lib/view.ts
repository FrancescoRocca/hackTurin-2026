import type {
  AnomalyHour,
  Counts,
  DetectionEvent,
  HourBucket,
  Intersection,
  NodeSnapshot,
  NodeStatus,
} from "../data/types";
import { addCounts, emptyCounts, totalCounts } from "../data/types";
import { anomalyKey } from "./verify";

/** A single read of a node, ready to draw. */
export interface NodeView {
  node: Intersection;
  status: NodeStatus;
  /** Passes in the last 24 hours, including this session. */
  total: number;
  /** Passes in the last minute. */
  rate: number;
  today: Counts;
  yesterday: Counts;
  /** Percentage change on the previous day, 0 when not comparable. */
  deltaPct: number;
  hourly: HourBucket[];
  events: DetectionEvent[];
  anomalies: AnomalyHour[];
  /** Hours already verified by an operator. */
  verifiedKeys: Set<string>;
  /** Verdicts recorded on this node. */
  verifications: NodeSnapshot["verifications"];
}

export interface BuildInput {
  snapshot: NodeSnapshot;
  added: Counts;
  events: DetectionEvent[];
  hourly: HourBucket[];
  total: number;
  rate: number;
}

export function buildNodeView(input: BuildInput): NodeView {
  const { snapshot, events, hourly, total, rate } = input;
  const verifiedKeys = new Set(snapshot.verifications.map((v) => v.key));
  const anomalies = snapshot.anomalies;
  return {
    node: snapshot.node,
    status: snapshot.status,
    total,
    rate,
    today: hourly.reduce((acc, h) => addCounts(acc, h.counts), emptyCounts()),
    yesterday: snapshot.yesterday,
    deltaPct:
      snapshot.yesterdayTotal > 0
        ? ((total - snapshot.yesterdayTotal) / snapshot.yesterdayTotal) * 100
        : 0,
    hourly,
    events,
    anomalies,
    verifiedKeys,
    verifications: snapshot.verifications,
  };
}

export function openAnomalies(view: NodeView): AnomalyHour[] {
  return view.anomalies.filter((a) => !view.verifiedKeys.has(anomalyKey(view.node.id, a.ts, a.cls)));
}

/** Nodes that need a person: a silent sensor, or unusual hours nobody has looked at yet. */
export function needingAttention(views: NodeView[]): NodeView[] {
  return views.filter((v) => !v.status.online || openAnomalies(v).length > 0);
}

/**
 * The node after `currentId` in the list, wrapping around at the end.
 * If `currentId` is not in the list, starts from the first.
 */
export function nextAfter<T extends { node: { id: string } }>(list: T[], currentId: string | null): T | undefined {
  if (list.length === 0) return undefined;
  const at = list.findIndex((x) => x.node.id === currentId);
  return list[(at + 1) % list.length];
}

export function peakTsOf(hourly: HourBucket[]): number | null {
  let best: number | null = null;
  let bestTotal = 0;
  for (const h of hourly) {
    if (h.missing) continue;
    const t = totalCounts(h.counts);
    if (t > bestTotal) {
      bestTotal = t;
      best = h.ts;
    }
  }
  return best;
}
