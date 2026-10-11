import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { source } from "./data/adapter";
import { useTraffic } from "./hooks/useTraffic";
import { addCounts, emptyCounts, type Counts, type Verdict } from "./data/types";
import { corridorTotalM } from "./lib/geo";
import {
  buildNodeView,
  needingAttention,
  nextAfter,
  openAnomalies,
  peakTsOf,
  type NodeView,
} from "./lib/view";
import { loadOperator, saveOperator } from "./lib/verify";
import { CLASS_LABEL } from "./lib/classes";
import { hhmmss, meters, num, since } from "./lib/format";
import { SummaryBar } from "./components/SummaryBar";
import { CorridorList } from "./components/CorridorList";
import { PlanMap, type MarkerState } from "./components/PlanMap";
import { NodeDetail } from "./components/NodeDetail";
import { NetworkChart } from "./components/NetworkChart";
import { SimulatedChip } from "./components/SimulatedChip";
import { ShortcutsButton } from "./components/ShortcutsButton";
import { LoadingSkeleton } from "./components/LoadingSkeleton";

/** Page clock: relative times must keep ticking. */
function useNow(intervalMs = 1000): number {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    const t = setInterval(() => setNow(Date.now()), intervalMs);
    return () => clearInterval(t);
  }, [intervalMs]);
  return now;
}

function stateOfView(v: NodeView | undefined): MarkerState {
  if (!v || !v.status.online) return "off";
  return openAnomalies(v).length > 0 ? "warn" : "ok";
}

export function App() {
  const traffic = useTraffic(source);
  const now = useNow(1000);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [operator, setOperator] = useState(() => loadOperator());
  const [announce, setAnnounce] = useState("");
  const corridorM = useMemo(() => corridorTotalM(), []);

  const views: NodeView[] = useMemo(
    () =>
      traffic.nodes
        .map((node) => {
          const live = traffic.live[node.id];
          if (!live) return null;
          return buildNodeView({
            snapshot: live.snapshot,
            added: live.added,
            events: live.events,
            hourly: traffic.hourlyOf(node.id),
            total: traffic.totalOf(node.id),
            rate: traffic.rateOf(node.id),
          });
        })
        .filter((v): v is NodeView => v !== null),
    [traffic],
  );

  // On load, go straight to the intersection that needs someone.
  useEffect(() => {
    if (selectedId !== null || views.length === 0) return;
    const first = views.find((v) => !v.status.online) ?? views.find((v) => stateOfView(v) === "warn");
    setSelectedId((first ?? views[0]).node.id);
  }, [views, selectedId]);

  // When the page scrolls (narrow screens) the detail sits far below the list
  // and the map, so a choice made there brings the detail into view.
  const selectNode = useCallback((id: string) => {
    setSelectedId(id);
    if (!matchMedia("(max-width: 1150px)").matches) return;
    const reduced = matchMedia("(prefers-reduced-motion: reduce)").matches;
    requestAnimationFrame(() =>
      document.getElementById("detail")?.scrollIntoView({ behavior: reduced ? "auto" : "smooth", block: "start" }),
    );
  }, []);

  const selectedIndex = Math.max(0, views.findIndex((v) => v.node.id === selectedId));
  const selected = views[selectedIndex] ?? null;

  const network = useMemo(() => {
    const base = views[0]?.hourly ?? [];
    const sums: Counts[] = base.map(() => emptyCounts());
    const flagged = new Set<number>();
    let total = 0;
    let rate = 0;
    let totals = emptyCounts();
    for (const v of views) {
      total += v.total;
      rate += v.status.online ? v.rate : 0;
      totals = addCounts(totals, v.today);
      if (v.status.online) openAnomalies(v).forEach((a) => flagged.add(a.ts));
      v.hourly.forEach((h, i) => {
        if (sums[i]) sums[i] = addCounts(sums[i], h.counts);
      });
    }
    const hourly = base.map((h, i) => ({ ts: h.ts, counts: sums[i] ?? emptyCounts() }));
    const peakTs = peakTsOf(hourly);
    return { hourly, flagged, total, rate, totals, peakTs };
  }, [views]);

  // The map receives a new object only when a marker state changes, so the
  // one-second clock tick never touches it.
  const nextStates = Object.fromEntries(views.map((v) => [v.node.id, stateOfView(v)])) as Record<string, MarkerState>;
  const statesRef = useRef({ key: "", value: nextStates });
  const statesKey = JSON.stringify(nextStates);
  if (statesRef.current.key !== statesKey) statesRef.current = { key: statesKey, value: nextStates };
  const markerStates = statesRef.current.value;
  const selectedLabel = selected
    ? selected.status.online
      ? `${selected.node.name} · ${num(selected.total)}`
      : `${selected.node.name} · not responding`
    : "";

  const handleOperator = useCallback((name: string) => {
    setOperator(name);
    saveOperator(name);
  }, []);

  const handleVerify = useCallback(
    async (input: { key: string; verdict: Verdict; note: string }) => {
      if (!selected) return;
      await traffic.verify({
        nodeId: selected.node.id,
        key: input.key,
        verdict: input.verdict,
        note: input.note,
        operator: operator.trim() || "unnamed",
      });
      setAnnounce(
        `${selected.node.name}: ${input.verdict === "sensor_error" ? "marked as sensor error" : "count confirmed"}.`,
      );
    },
    [selected, traffic, operator],
  );

  // Screen-reader announcements are throttled: one summary every 20 seconds,
  // not one line per pass.
  const announced = useRef<{ id: string; total: number; at: number } | null>(null);
  useEffect(() => {
    if (!selected || traffic.paused) return;
    const prev = announced.current;
    if (!prev || prev.id !== selected.node.id) {
      announced.current = { id: selected.node.id, total: selected.total, at: now };
      return;
    }
    if (now - prev.at < 20_000) return;
    const delta = selected.total - prev.total;
    announced.current = { id: prev.id, total: selected.total, at: now };
    const last = selected.events[0];
    if (delta > 0 && last) {
      setAnnounce(
        `${selected.node.name}: ${delta === 1 ? "1 new pass" : `${delta} new passes`}, the last is a ${CLASS_LABEL[last.cls]}.`,
      );
    }
  }, [selected, now, traffic.paused]);

  // A sensor that stops or resumes responding must be announced, on any intersection.
  const onlineBefore = useRef(new Map<string, boolean>());
  useEffect(() => {
    for (const v of views) {
      const was = onlineBefore.current.get(v.node.id);
      if (was !== undefined && was !== v.status.online) {
        setAnnounce(v.status.online ? `${v.node.name} is responding again.` : `${v.node.name} is not responding.`);
      }
      onlineBefore.current.set(v.node.id, v.status.online);
    }
  }, [views]);

  // Shortcuts: P pauses, N goes to the next intersection that needs someone.
  const attentionNodes = needingAttention(views);
  const nextAttentionId = nextAfter(attentionNodes, selected?.node.id ?? null)?.node.id ?? null;
  const shortcutRef = useRef({ paused: traffic.paused, setPaused: traffic.setPaused, nextAttentionId, select: selectNode });
  shortcutRef.current = { paused: traffic.paused, setPaused: traffic.setPaused, nextAttentionId, select: selectNode };
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.ctrlKey || e.metaKey || e.altKey) return;
      const t = e.target as HTMLElement | null;
      if (t && (t.isContentEditable || /^(INPUT|TEXTAREA|SELECT)$/.test(t.tagName))) return;
      const k = e.key.toLowerCase();
      if (k === "p") {
        shortcutRef.current.setPaused(!shortcutRef.current.paused);
      } else if (k === "n" && shortcutRef.current.nextAttentionId) {
        shortcutRef.current.select(shortcutRef.current.nextAttentionId);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  const liveText = traffic.paused
    ? "Paused: numbers are not updating"
    : traffic.lastEventAt
      ? `Live · last pass ${since(traffic.lastEventAt, now)}`
      : "Live · waiting for the first pass";

  const topbar = (
    <header className="topbar">
      <div className="brand">
        <span className="wordmark">larp</span>
        <div className="brand-text">
          <h1>Traffic on Corso Bolzano</h1>
          <p>
            Turin, Porta Susa · {traffic.nodeCount || 6} intersections over {meters(corridorM)}
            <span className="brand-claim">counts only: no image leaves the sensor</span>
          </p>
        </div>
      </div>
      <div className="topbar-right">
        {source.synthetic ? <SimulatedChip /> : null}
        <ShortcutsButton />
        <span className={`live ${traffic.paused ? "paused" : ""}`}>
          <i aria-hidden="true" />
          {liveText}
          <span className="live-time" aria-hidden="true">
            {hhmmss(now)}
          </span>
        </span>
        <button
          type="button"
          className="btn on-dark"
          aria-pressed={traffic.paused}
          aria-keyshortcuts="P"
          onClick={() => traffic.setPaused(!traffic.paused)}
        >
          {traffic.paused ? "Resume" : "Pause"}
        </button>
      </div>
    </header>
  );

  if (traffic.error) {
    return (
      <div className="app">
        {topbar}
        <main className="error-wrap">
          <div className="error-box" role="alert">
            <h2>Can't read the sensors</h2>
            <p>{traffic.error}. No numbers are shown until reading succeeds.</p>
            <button type="button" className="btn primary" onClick={traffic.refresh}>
              Retry
            </button>
          </div>
        </main>
      </div>
    );
  }

  return (
    <div className="app">
      <a className="skip" href="#detail">
        Skip to intersection detail
      </a>
      {topbar}

      {!traffic.ready ? (
        <LoadingSkeleton />
      ) : (
        <>
          <SummaryBar
            views={views}
            networkTotal={network.total}
            networkRate={network.rate}
            now={now}
            selectedId={selected?.node.id ?? null}
            onSelect={selectNode}
          />
          <main className="work">
            <CorridorList views={views} now={now} selectedId={selected?.node.id ?? null} onSelect={selectNode} />
            <div className="center">
              <PlanMap
                nodes={traffic.nodes}
                selectedId={selected?.node.id ?? null}
                onSelect={selectNode}
                states={markerStates}
                selectedLabel={selectedLabel}
              />
              <NetworkChart
                hourly={network.hourly}
                flagged={network.flagged}
                peakTs={network.peakTs}
                totals={network.totals}
              />
            </div>
            {selected ? (
              <NodeDetail
                key={selected.node.id}
                view={selected}
                index={selectedIndex}
                operator={operator}
                onOperator={handleOperator}
                onVerify={handleVerify}
                now={now}
                synthetic={source.synthetic}
              />
            ) : (
              <section className="panel detail" id="detail" tabIndex={-1}>
                <p className="empty">Choose an intersection from the list or the map.</p>
              </section>
            )}
          </main>
        </>
      )}

      <div className="sr" aria-live="polite" role="status">
        {announce}
      </div>
    </div>
  );
}
