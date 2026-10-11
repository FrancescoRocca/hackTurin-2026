import {
  addCounts,
  emptyCounts,
  totalCounts,
  type DetectionEvent,
  type HourBucket,
  type Intersection,
  type NodeSnapshot,
  type NodeStatus,
  type TrafficSource,
  type Verification,
  type VerifyRequest,
} from "./types";
import { SimulatedSource } from "./simulated";

/**
 * Seam for a real feed.
 *
 * The node (Arduino UNO Q + IMX219) classifies on board. A gateway exposes the
 * aggregated counts and the event stream; **no endpoint of this contract
 * carries images**, on purpose.
 *
 *   GET  {base}/nodes                       → Intersection[]
 *   GET  {base}/nodes/:id/status            → NodeStatus
 *   GET  {base}/nodes/:id/hourly?hours=24   → HourBucket[]
 *   GET  {base}/nodes/:id/events?n=60       → DetectionEvent[]
 *   GET  {base}/nodes/:id/anomalies         → AnomalyHour[]
 *   GET  {base}/nodes/:id/verifications     → Verification[]
 *   POST {base}/verifications               → Verification
 *   GET  {base}/stream  (text/event-stream) → DetectionEvent
 *
 * `snapshot` builds a single read from five calls, so the UI does not need to
 * know anything about the network. If the gateway answers in another shape,
 * this is the only file to change.
 */
export function createHttpSource(base: string): TrafficSource {
  const url = (path: string) => `${base.replace(/\/$/, "")}${path}`;

  async function get<T>(path: string): Promise<T> {
    const res = await fetch(url(path), { headers: { accept: "application/json" } });
    if (!res.ok) throw new Error(`${path} → ${res.status} ${res.statusText}`);
    return (await res.json()) as T;
  }

  let nodes: Intersection[] = [];

  return {
    kind: "http",
    synthetic: false,

    async listNodes() {
      if (nodes.length === 0) nodes = await get<Intersection[]>("/nodes");
      return nodes;
    },

    async snapshot(nodeId: string): Promise<NodeSnapshot> {
      const [status, hourly, events, anomalies, verifications] = await Promise.all([
        get<NodeStatus>(`/nodes/${nodeId}/status`),
        get<HourBucket[]>(`/nodes/${nodeId}/hourly?hours=24`),
        get<DetectionEvent[]>(`/nodes/${nodeId}/events?n=60`),
        get<NodeSnapshot["anomalies"]>(`/nodes/${nodeId}/anomalies`),
        get<Verification[]>(`/nodes/${nodeId}/verifications`),
      ]);
      const today = hourly.reduce((acc, h) => addCounts(acc, h.counts), emptyCounts());
      let peakHour: number | null = null;
      let peakHourTotal = 0;
      hourly.forEach((h) => {
        const t = totalCounts(h.counts);
        if (t > peakHourTotal) {
          peakHourTotal = t;
          peakHour = new Date(h.ts).getHours();
        }
      });
      const now = Date.now();
      return {
        node: nodes.find((n) => n.id === nodeId) ?? {
          id: nodeId,
          name: nodeId,
          street: "",
          lat: 0,
          lng: 0,
          arms: 0,
          note: "",
          installedAt: new Date().toISOString(),
          osmNode: 0,
        },
        status,
        hourly,
        today,
        yesterday: emptyCounts(),
        todayTotal: totalCounts(today),
        yesterdayTotal: 0,
        peakHour,
        peakHourTotal,
        currentRate: events.filter((e) => now - e.ts <= 60_000).length,
        events,
        anomalies,
        verifications,
      };
    },

    async verify(req: VerifyRequest): Promise<Verification> {
      const res = await fetch(url("/verifications"), {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify(req),
      });
      if (!res.ok) throw new Error(`verification rejected: ${res.status}`);
      return (await res.json()) as Verification;
    },

    stream(handler: (e: DetectionEvent) => void): () => void {
      const source = new EventSource(url("/stream"));
      source.onmessage = (ev) => {
        try {
          handler(JSON.parse(ev.data) as DetectionEvent);
        } catch {
          /* an unreadable line must not stop the stream */
        }
      };
      return () => source.close();
    },
  };
}

/** The active source. Today: simulated, declared as such in the interface. */
export const source: TrafficSource = new SimulatedSource();

export { SimulatedSource };
