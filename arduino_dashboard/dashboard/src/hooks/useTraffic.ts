import { useCallback, useEffect, useRef, useState } from "react";
import type {
  Counts,
  DetectionEvent,
  HourBucket,
  Intersection,
  NodeSnapshot,
  TrafficSource,
  Verdict,
} from "../data/types";
import { addCounts, emptyCounts, totalCounts } from "../data/types";

const FLUSH_MS = 500;
/**
 * The rate is measured over the last minute of real flow. A shorter window is
 * jumpy (a quiet node would flicker between 0 and 6 passes a minute), so while
 * the window is still filling it is blended with the average of the current
 * hour, and the number never reads zero just because the page is new.
 */
const RATE_WINDOW_MS = 60_000;
const RATE_SAMPLES = Math.round(RATE_WINDOW_MS / FLUSH_MS);
const LIVE_EVENTS_KEPT = 240;

interface NodeLive {
  snapshot: NodeSnapshot;
  /** Events received in this session, most recent first. */
  events: DetectionEvent[];
  /** Counts generated in this session, not yet folded into the base reading. */
  added: Counts;
  /** Counts per beat: the sum over the window is the per-minute rate. */
  window: number[];
  /** Passes per minute averaged over the current hour at load time. */
  baseRate: number;
}

export interface TrafficState {
  ready: boolean;
  error: string | null;
  nodes: Intersection[];
  live: Record<string, NodeLive>;
  /** Passes in the last minute. */
  rateOf: (nodeId: string) => number;
  /** Counts for the last 24 h, session included. */
  todayOf: (nodeId: string) => Counts;
  totalOf: (nodeId: string) => number;
  /** Hours of the day, session included, with the current hour last. */
  hourlyOf: (nodeId: string) => HourBucket[];
  nodeCount: number;
  lastEventAt: number | null;
  paused: boolean;
  setPaused: (p: boolean) => void;
  refresh: () => void;
  verify: (input: {
    nodeId: string;
    key: string;
    verdict: Verdict;
    note: string;
    operator: string;
  }) => Promise<void>;
}

/** Average passes per minute so far in the latest hourly bucket. */
function hourAverageRate(hourly: HourBucket[], at: number): number {
  const last = hourly[hourly.length - 1];
  if (!last || last.missing) return 0;
  const minutes = Math.max(1, (at - last.ts) / 60_000);
  return totalCounts(last.counts) / minutes;
}

function hourStart(ts: number): number {
  const d = new Date(ts);
  d.setMinutes(0, 0, 0);
  return d.getTime();
}

/**
 * Keeps the node reading and the event stream together.
 *
 * The base reading is snapshotted at load time; from then on the session owns
 * its own increments, so counts are not added twice and the per-minute rate
 * comes from the real flow instead of the profile.
 */
export function useTraffic(source: TrafficSource): TrafficState {
  const [nodes, setNodes] = useState<Intersection[]>([]);
  const [live, setLive] = useState<Record<string, NodeLive>>({});
  const [ready, setReady] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [paused, setPaused] = useState(false);
  const [lastEventAt, setLastEventAt] = useState<number | null>(null);
  const pending = useRef<DetectionEvent[]>([]);
  const pausedRef = useRef(false);
  /** Nodes that just started reporting again, to re-read and recompute their history. */
  const queueResync = useRef<string[]>([]);

  pausedRef.current = paused;

  const load = useCallback(async () => {
    try {
      const list = await source.listNodes();
      const snapshots = await Promise.all(list.map((n) => source.snapshot(n.id)));
      const next: Record<string, NodeLive> = {};
      for (const snapshot of snapshots) {
        next[snapshot.node.id] = {
          snapshot,
          events: [],
          added: emptyCounts(),
          window: [],
          baseRate: hourAverageRate(snapshot.hourly, Date.now()),
        };
      }
      setNodes(list);
      setLive(next);
      setReady(true);
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "failed to read nodes");
    }
  }, [source]);

  useEffect(() => {
    void load();
  }, [load]);

  useEffect(() => {
    return source.stream((e) => {
      if (pausedRef.current) return;
      pending.current.push(e);
    });
  }, [source]);

  useEffect(() => {
    const timer = setInterval(() => {
      if (pausedRef.current) return;
      const batch = pending.current;
      pending.current = [];
      setLive((prev) => {
        if (Object.keys(prev).length === 0) return prev;
        const nowHour = hourStart(Date.now());
        const next: Record<string, NodeLive> = {};
        // One rate sample per beat, even when the flow is idle, so the rate decays.
        for (const [id, cur] of Object.entries(prev)) {
          const hourly = cur.snapshot.hourly;
          if (hourly.length > 1 && hourly[hourly.length - 1].ts !== nowHour) {
            // Hour change: session increments close out the elapsed hour.
            const closed = hourly[hourly.length - 1];
            const rolled: HourBucket[] = [
              ...hourly.slice(1, -1),
              { ts: closed.ts, counts: addCounts(closed.counts, cur.added), missing: closed.missing },
              { ts: nowHour, counts: emptyCounts() },
            ];
            next[id] = {
              snapshot: { ...cur.snapshot, hourly: rolled },
              events: cur.events,
              added: emptyCounts(),
              window: [0],
              baseRate: cur.baseRate,
            };
          } else {
            next[id] = { ...cur, window: [...cur.window, 0].slice(-RATE_SAMPLES) };
          }
        }
        const touched = new Set(batch.map((e) => e.nodeId));
        const justOnline: string[] = [];
        if (batch.length > 0) {
          for (const id of touched) {
            if (prev[id] && !prev[id].snapshot.status.online) justOnline.push(id);
          }
        }
        for (const id of touched) {
          const cur = next[id];
          if (!cur) continue;
          const added = { ...cur.added };
          const fresh: DetectionEvent[] = [];
          for (const e of batch) {
            if (e.nodeId !== id) continue;
            added[e.cls] += 1;
            fresh.push(e);
          }
          const window = [...cur.window];
          window[window.length - 1] = (window[window.length - 1] ?? 0) + fresh.length;
          const lastTs = fresh[fresh.length - 1]?.ts ?? cur.snapshot.status.lastBeat;
          next[id] = {
            ...cur,
            added,
            window,
            events: [...fresh.reverse(), ...cur.events].slice(0, LIVE_EVENTS_KEPT),
            snapshot: {
              ...cur.snapshot,
              // Hearing a pass from a silent node means it is reporting again.
              status: { ...cur.snapshot.status, online: true, lastBeat: lastTs },
            },
          };
        }
        if (justOnline.length > 0) queueResync.current.push(...justOnline);
        return next;
      });
      if (batch.length > 0) setLastEventAt(batch[batch.length - 1].ts);
    }, FLUSH_MS);
    return () => clearInterval(timer);
  }, []);

  const hourlyOf = useCallback(
    (nodeId: string): HourBucket[] => {
      const cur = live[nodeId];
      if (!cur) return [];
      const hourly = cur.snapshot.hourly;
      if (hourly.length === 0) return hourly;
      const last = hourly.length - 1;
      const counts = addCounts(hourly[last].counts, cur.added);
      const merged = [...hourly];
      merged[last] = {
        ts: hourly[last].ts,
        counts,
        missing: hourly[last].missing && totalCounts(counts) === 0 ? true : undefined,
      };
      return merged;
    },
    [live],
  );

  const todayOf = useCallback(
    (nodeId: string): Counts => {
      const hourly = hourlyOf(nodeId);
      return hourly.reduce((acc, h) => addCounts(acc, h.counts), emptyCounts());
    },
    [hourlyOf],
  );

  const totalOf = useCallback((nodeId: string) => totalCounts(todayOf(nodeId)), [todayOf]);

  const rateOf = useCallback(
    (nodeId: string): number => {
      const cur = live[nodeId];
      if (!cur) return 0;
      const sum = cur.window.reduce((a, b) => a + b, 0);
      const observedMs = Math.max(1, cur.window.length) * FLUSH_MS;
      const observed = (sum * 60_000) / observedMs;
      // Blend with the hourly average until a full window has been observed.
      const weight = Math.min(1, cur.window.length / RATE_SAMPLES);
      return Math.round(weight * observed + (1 - weight) * cur.baseRate);
    },
    [live],
  );

  /** Re-reads a single node without touching the session increments. */
  const resnapshot = useCallback(
    async (nodeId: string) => {
      try {
        const snapshot = await source.snapshot(nodeId);
        setLive((prev) =>
          prev[nodeId] ? { ...prev, [nodeId]: { ...prev[nodeId], snapshot } } : prev,
        );
      } catch {
        /* the next read will retry */
      }
    },
    [source],
  );

  // When a node starts reporting again its history must be recomputed: the
  // silence is over and the hours to verify must be looked up on the full field.
  useEffect(() => {
    const timer = setInterval(() => {
      const ids = Array.from(new Set(queueResync.current));
      if (ids.length === 0) return;
      queueResync.current = [];
      ids.forEach((id) => void resnapshot(id));
    }, 1200);
    return () => clearInterval(timer);
  }, [resnapshot]);

  const verify = useCallback(
    async (input: {
      nodeId: string;
      key: string;
      verdict: Verdict;
      note: string;
      operator: string;
    }) => {
      const record = await source.verify(input);
      setLive((prev) => {
        const cur = prev[input.nodeId];
        if (!cur) return prev;
        return {
          ...prev,
          [input.nodeId]: {
            ...cur,
            snapshot: {
              ...cur.snapshot,
              verifications: [
                ...cur.snapshot.verifications.filter((v) => v.key !== record.key),
                record,
              ],
            },
          },
        };
      });
    },
    [source],
  );

  return {
    ready,
    error,
    nodes,
    live,
    rateOf,
    todayOf,
    hourlyOf,
    totalOf,
    nodeCount: nodes.length,
    lastEventAt,
    paused,
    setPaused,
    refresh: () => void load(),
    verify,
  };
}
