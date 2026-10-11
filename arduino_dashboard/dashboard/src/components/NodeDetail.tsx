import { useState } from "react";
import { CLASS_LABEL, CLASS_ORDER, CLASS_PEN } from "../lib/classes";
import type { NodeView } from "../lib/view";
import { openAnomalies, peakTsOf } from "../lib/view";
import { HourField } from "./HourField";
import { Verification } from "./Verification";
import { dec1, duration, hhmm, hhmmss, num, perMinute, share, signedShare, since } from "../lib/format";
import { totalCounts, type Verdict } from "../data/types";

interface NodeDetailProps {
  view: NodeView;
  index: number;
  operator: string;
  onOperator: (name: string) => void;
  onVerify: (input: { key: string; verdict: Verdict; note: string }) => Promise<void>;
  now: number;
  synthetic: boolean;
}

/**
 * The detail of an intersection, top to bottom in the order of the questions:
 * is the sensor working? how much has passed? what? when? is there anything
 * to review?
 */
export function NodeDetail({ view, index, operator, onOperator, onVerify, now, synthetic }: NodeDetailProps) {
  const online = view.status.online;
  const [saved, setSaved] = useState<string | null>(null);
  const peakTs = peakTsOf(view.hourly);
  const peakTotal = totalCounts(view.hourly.find((h) => h.ts === peakTs)?.counts ?? view.today);
  const open = openAnomalies(view);
  const urgent = online && open.length > 0;
  const maxClass = Math.max(1, ...CLASS_ORDER.map((c) => view.today[c]));

  // If there is something to decide, the decision sits right below the sensor
  // status; if not, the block stays at the end of the story and says all is well.
  // A silent sensor has nothing to review: the status strip already says so.
  const checksBlock = !online ? null : (
    <section className="block checks-block" id="to-review" aria-labelledby="checks-title">
      <h3 id="checks-title">To review</h3>
      <Verification
        view={view}
        operator={operator}
        onOperator={onOperator}
        onVerify={onVerify}
        now={now}
        saved={saved}
        onSaved={setSaved}
      />
    </section>
  );

  return (
    <section className="panel detail" id="detail" tabIndex={-1} aria-labelledby="detail-title">
      <header className="detail-head">
        <span className={`stop-dot big ${!online ? "off" : open.length > 0 ? "warn" : "ok"}`} aria-hidden="true">
          {index + 1}
        </span>
        <div>
          <h2 id="detail-title">{view.node.name}</h2>
          <p className="detail-where">
            {view.node.street} · {view.node.arms}-arm intersection
          </p>
        </div>
      </header>

      <div className={`health ${online ? "ok" : "off"}`}>
        <span className="health-dot" aria-hidden="true" />
        {online ? (
          <span>
            <b>Sensor active</b> · last signal {since(view.status.lastBeat, now)}
          </span>
        ) : (
          <span>
            <b>The sensor is not responding</b> · last signal {since(view.status.lastBeat, now)}.
            Counts are frozen at that point. Check its power and network connection.
          </span>
        )}
      </div>

      <dl className="figures">
        <div>
          <dt>{online ? "Passes in the last 24 hours" : "Passes counted before it stopped"}</dt>
          <dd>{view.total > 0 ? num(view.total) : "—"}</dd>
        </div>
        <div>
          <dt>Per minute, now</dt>
          <dd>{online ? perMinute(view.rate) : "—"}</dd>
        </div>
        <div>
          <dt>Versus yesterday</dt>
          <dd>{online && view.total > 0 ? signedShare(view.deltaPct) : "—"}</dd>
        </div>
      </dl>

      {urgent ? checksBlock : null}

      <section className="block" aria-labelledby="mix-title">
        <h3 id="mix-title">What passed</h3>
        {view.total > 0 ? (
          <div className="mix">
            {CLASS_ORDER.map((c) => {
              const value = view.today[c];
              return (
                <div className="mix-row" key={c}>
                  <span className="swatch" style={{ background: CLASS_PEN[c] }} aria-hidden="true" />
                  <span className="mix-label">{CLASS_LABEL[c]}</span>
                  <span className="mix-bar" aria-hidden="true">
                    <i style={{ width: `${(value / maxClass) * 100}%`, background: CLASS_PEN[c] }} />
                  </span>
                  <span className="mix-val">{num(value)}</span>
                  <span className="mix-pc">{share(value, view.total)}</span>
                </div>
              );
            })}
          </div>
        ) : (
          <p className="empty">No passes recorded in the last 24 hours.</p>
        )}
      </section>

      <section className="block" aria-labelledby="hours-title">
        <div className="block-head">
          <h3 id="hours-title">Hour by hour</h3>
          <span>
            {peakTs ? `busiest at ${hhmm(peakTs)} (${num(peakTotal)})` : "no data"}
          </span>
        </div>
        <HourField
          hourly={view.hourly}
          flagged={new Set(open.map((a) => a.ts))}
          label={
            view.total > 0
              ? `Passes hour by hour over the last 24 hours: ${num(view.total)} in total, peak at ${peakTs ? hhmm(peakTs) : "—"}`
              : "No data in the last 24 hours"
          }
        />
      </section>

      {urgent ? null : checksBlock}

      <details className="block fold">
        <summary>
          <h3 id="feed-title">Latest passes</h3>
          <span>{view.events.length > 0 ? `${Math.min(6, view.events.length)} most recent` : "none"}</span>
        </summary>
        {view.events.length > 0 ? (
          <>
            <table className="feed" aria-labelledby="feed-title">
              <thead>
                <tr>
                  <th scope="col">Time</th>
                  <th scope="col">Type</th>
                  <th scope="col">Confidence</th>
                </tr>
              </thead>
              <tbody>
                {view.events.slice(0, 6).map((e) => (
                  <tr key={e.id}>
                    <td>{hhmmss(e.ts)}</td>
                    <td>
                      <span className="swatch sm" style={{ background: CLASS_PEN[e.cls] }} aria-hidden="true" />
                      {CLASS_LABEL[e.cls]}
                    </td>
                    <td>{dec1(e.confidence * 100)}%</td>
                  </tr>
                ))}
              </tbody>
            </table>
            <p className="fold-note">Confidence: how sure the sensor is of the type it recognised.</p>
          </>
        ) : (
          <p className="empty">
            {online ? "Waiting for the next pass." : "No passes: the sensor is off or disconnected."}
          </p>
        )}
      </details>

      <footer className="detail-foot">
        <p>
          The sensor recognises vehicles on board and sends only counts: no photo
          or video leaves the device.
          {synthetic ? " In this demo the counts are simulated." : ""}
        </p>
        <details className="fold small">
          <summary>Sensor details</summary>
          <p className="meta">
            {view.node.id} · Arduino UNO Q · firmware {view.status.firmware} · in service for{" "}
            {duration(view.status.uptimeMs)} · position from OpenStreetMap, node {view.node.osmNode}
          </p>
        </details>
      </footer>
    </section>
  );
}
