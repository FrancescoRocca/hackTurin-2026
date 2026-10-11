import { useState } from "react";
import type { AnomalyHour, Verdict } from "../data/types";
import { CLASS_PLURAL } from "../lib/classes";
import { anomalyKey } from "../lib/verify";
import type { NodeView } from "../lib/view";
import { hhmm, num, since, signedShare } from "../lib/format";

interface VerificationProps {
  view: NodeView;
  operator: string;
  onOperator: (name: string) => void;
  onVerify: (input: { key: string; verdict: Verdict; note: string }) => Promise<void>;
  now: number;
  /** Confirmation of the last saved verdict. Lives in the parent because this block moves when the last open hour is reviewed. */
  saved: string | null;
  onSaved: (message: string) => void;
}

const HOUR = 3_600_000;

function sentence(a: AnomalyHour): string {
  return `Between ${hhmm(a.ts)} and ${hhmm(a.ts + HOUR)}, ${num(a.observed)} ${CLASS_PLURAL[a.cls]} passed. Usually at that hour it is about ${num(a.expected)}.`;
}

function deltaOf(a: AnomalyHour): string {
  if (a.expected <= 0) return a.z > 0 ? "more than usual" : "less than usual";
  return `${signedShare(((a.observed - a.expected) / a.expected) * 100)} versus usual`;
}

/**
 * Unusual hours: a count far from the intersection's history. There is no
 * image to look at (the sensor sends none), so the decision rests on the
 * number: is it plausible, or is it a sensor error?
 */
export function Verification({ view, operator, onOperator, onVerify, now, saved, onSaved }: VerificationProps) {
  const [notes, setNotes] = useState<Record<string, string>>({});
  /** Key of the verdict currently being saved. */
  const [busy, setBusy] = useState<string | null>(null);
  /** Key → message, for a save that failed. */
  const [failed, setFailed] = useState<Record<string, string>>({});

  const decide = async (key: string, verdict: Verdict, note: string) => {
    setBusy(key);
    setFailed((f) => {
      const { [key]: _gone, ...rest } = f;
      return rest;
    });
    try {
      await onVerify({ key, verdict, note });
      const a = view.anomalies.find((x) => anomalyKey(view.node.id, x.ts, x.cls) === key);
      const what = a ? `${hhmm(a.ts)} ${CLASS_PLURAL[a.cls]}` : "Count";
      onSaved(`${what}: marked as ${verdict === "confirmed" ? "correct" : "a sensor error"}.`);
    } catch (e) {
      const why = e instanceof Error && e.message ? ` (${e.message})` : "";
      setFailed((f) => ({ ...f, [key]: `Could not save the verdict${why}. Try again.` }));
    } finally {
      setBusy(null);
    }
  };
  const keyOf = (a: AnomalyHour) => anomalyKey(view.node.id, a.ts, a.cls);
  const open = view.anomalies.filter((a) => !view.verifiedKeys.has(keyOf(a)));
  const closed = view.anomalies.filter((a) => view.verifiedKeys.has(keyOf(a)));

  return (
    <div className="checks">
      {saved ? (
        <p className="checks-saved" role="status">
          {saved}
        </p>
      ) : null}
      {open.length === 0 ? (
        <p className="empty">
          {view.anomalies.length === 0
            ? "No unusual hours: the counts of the last 24 hours are in line with previous weeks."
            : "All unusual hours have been reviewed."}
        </p>
      ) : (
        <>
          <details className="checks-intro">
            <summary>What makes an hour unusual?</summary>
            <p>
              Its count is far from the same hour over the previous 7 days. It may be real
              traffic (an event, an accident) or a sensor error: you decide.
            </p>
          </details>
          <div className="operator">
            <label htmlFor="operator">Your name</label>
            <input
              id="operator"
              className="input"
              value={operator}
              placeholder="e.g. Marco"
              autoComplete="name"
              aria-describedby="operator-hint"
              onChange={(e) => onOperator(e.target.value)}
            />
            <small id="operator-hint">
              {operator.trim() ? "Signs your verdicts." : "If left empty, verdicts are signed “unnamed”."}
            </small>
          </div>
          <ul className="check-list">
            {open.map((a) => {
              const key = keyOf(a);
              return (
                <li className="check" key={key}>
                  <div className="check-head">
                    <b>
                      <i className="key-flag" aria-hidden="true" />
                      {hhmm(a.ts)}
                    </b>
                    <span className={`check-delta ${a.z > 0 ? "up" : "down"}`}>{deltaOf(a)}</span>
                  </div>
                  <p>{sentence(a)}</p>
                  <input
                    className="input"
                    aria-label={`Note on the ${hhmm(a.ts)} count (optional)`}
                    placeholder="Note (optional)"
                    value={notes[key] ?? ""}
                    onChange={(e) => setNotes((n) => ({ ...n, [key]: e.target.value }))}
                  />
                  <div className="check-actions">
                    <button
                      type="button"
                      className="btn"
                      disabled={busy !== null}
                      onClick={() => void decide(key, "confirmed", notes[key] ?? "")}
                    >
                      It's correct
                    </button>
                    <button
                      type="button"
                      className="btn danger"
                      disabled={busy !== null}
                      onClick={() => void decide(key, "sensor_error", notes[key] ?? "")}
                    >
                      It's a sensor error
                    </button>
                    {busy === key ? <span className="check-busy">Saving…</span> : null}
                  </div>
                  {failed[key] ? (
                    <p className="form-error" role="alert">
                      {failed[key]}
                    </p>
                  ) : null}
                </li>
              );
            })}
          </ul>
          <p className="checks-effect">
            Verdicts are signed with your name and never change the counts. You can revise one
            under “already reviewed”.
          </p>
        </>
      )}

      {closed.length > 0 ? (
        <details className="done-list">
          <summary>
            {closed.length === 1 ? "1 hour already reviewed" : `${closed.length} hours already reviewed`}
          </summary>
          <ul>
            {closed.map((a) => {
              const v = view.verifications.find((x) => x.key === keyOf(a));
              const wrong = v?.verdict === "sensor_error";
              return (
                <li key={keyOf(a)}>
                  <span>
                    <b>{hhmm(a.ts)}</b> {CLASS_PLURAL[a.cls]} ·{" "}
                    <span className={wrong ? "state-off" : "state-ok"}>
                      {wrong ? "sensor error" : "correct"}
                    </span>
                    <small>
                      {v ? ` — ${v.operator || "unnamed"}, ${since(v.at, now)}` : ""}
                      {v?.note ? ` · “${v.note}”` : ""}
                    </small>
                  </span>
                  {v ? (
                    <button
                      type="button"
                      className="btn link"
                      disabled={busy !== null}
                      onClick={() =>
                        void decide(keyOf(a), wrong ? "confirmed" : "sensor_error", v.note)
                      }
                    >
                      {wrong ? "Mark as correct" : "Mark as error"}
                    </button>
                  ) : null}
                  {failed[keyOf(a)] ? (
                    <span className="form-error" role="alert">
                      {failed[keyOf(a)]}
                    </span>
                  ) : null}
                </li>
              );
            })}
          </ul>
        </details>
      ) : null}
    </div>
  );
}
