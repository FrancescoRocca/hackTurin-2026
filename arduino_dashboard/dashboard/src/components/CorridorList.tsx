import { useRef } from "react";
import type { NodeView } from "../lib/view";
import { openAnomalies } from "../lib/view";
import { elapsed, num, perMinute } from "../lib/format";

interface CorridorListProps {
  views: NodeView[];
  now: number;
  selectedId: string | null;
  onSelect: (id: string) => void;
}

/**
 * The six intersections as the stops of a line, with north at the top as on
 * the map: each stop's number is the same as its marker's.
 * Each stop says whether the sensor responds, how much has passed in the last
 * 24 hours and whether there is anything to review. Arrow keys walk the list too.
 */
export function CorridorList({ views, now, selectedId, onSelect }: CorridorListProps) {
  const refs = useRef(new Map<string, HTMLButtonElement>());
  // Data runs south to north; the list reads from the top like the map.
  const shown = [...views].reverse();

  const move = (to: number) => {
    const view = shown[Math.min(shown.length - 1, Math.max(0, to))];
    if (!view) return;
    onSelect(view.node.id);
    refs.current.get(view.node.id)?.focus();
  };

  return (
    <section className="panel corridor" aria-labelledby="corridor-title">
      <header className="panel-head">
        <h2 id="corridor-title">Intersections</h2>
        <span className="panel-sub">north at the top, as on the map</span>
      </header>

      {views.length === 0 ? (
        <p className="empty">No sensors connected to the network.</p>
      ) : (
        <div className="line" role="listbox" aria-label="Monitored intersections, north to south">
          {shown.map((view, index) => {
            const selected = view.node.id === selectedId;
            const online = view.status.online;
            const open = online ? openAnomalies(view).length : 0;
            const state = !online ? "off" : open > 0 ? "warn" : "ok";
            return (
              <button
                key={view.node.id}
                ref={(el) => {
                  if (el) refs.current.set(view.node.id, el);
                  else refs.current.delete(view.node.id);
                }}
                type="button"
                role="option"
                aria-selected={selected}
                tabIndex={selected || (selectedId === null && index === 0) ? 0 : -1}
                className={`stop ${state}`}
                onClick={() => onSelect(view.node.id)}
                onKeyDown={(e) => {
                  const keys: Record<string, number> = {
                    ArrowDown: index + 1,
                    ArrowUp: index - 1,
                    Home: 0,
                    End: shown.length - 1,
                  };
                  if (e.key in keys) {
                    e.preventDefault();
                    move(keys[e.key]);
                  }
                }}
              >
                <span className="stop-dot" aria-hidden="true">
                  {views.length - index}
                </span>
                <span className="stop-body">
                  <span className="stop-name">{view.node.name}</span>
                  <span className="stop-state">
                    {!online ? (
                      <span className="state-off">Not responding</span>
                    ) : open > 0 ? (
                      <span className="state-warn">
                        {open === 1 ? "1 hour to review" : `${open} hours to review`}
                      </span>
                    ) : view.anomalies.length > 0 ? (
                      <span className="state-ok">Reviewed</span>
                    ) : (
                      <span className="state-ok">All normal</span>
                    )}
                  </span>
                </span>
                <span className={`stop-count${online ? "" : " frozen"}`}>
                  <b>{view.total > 0 ? num(view.total) : "—"}</b>
                  <small>
                    {online
                      ? `${perMinute(view.rate)}/min`
                      : `stopped for ${elapsed(view.status.lastBeat, now)}`}
                  </small>
                </span>
              </button>
            );
          })}
        </div>
      )}
      <p className="corridor-foot">Numbers: passes in the last 24 hours.</p>
    </section>
  );
}
