import { useMemo } from "react";
import { CLASS_LABEL, CLASS_ORDER, CLASS_PEN } from "../lib/classes";
import type { HourBucket } from "../data/types";
import { totalCounts } from "../data/types";
import { hhmm, num } from "../lib/format";

interface HourFieldProps {
  hourly: HourBucket[];
  /** Unusual hours still to review: marked with a triangle. */
  flagged?: Set<number>;
  label: string;
  /** Chart height in px. */
  height?: number;
}

/**
 * Passes hour by hour: twenty-four columns stacked by class, the most recent
 * on the right. An hour with no data is hatched, not drawn as a zero. The
 * current hour is still partial and appears lighter; the legend says so.
 *
 * The values are also in a visually hidden table, for anyone who cannot hover
 * over the chart.
 */
export function HourField({ hourly, flagged, label, height = 92 }: HourFieldProps) {
  const max = useMemo(
    () => Math.max(1, ...hourly.map((h) => totalCounts(h.counts))),
    [hourly],
  );
  const missing = hourly.filter((h) => h.missing).length;
  const hasFlag = hourly.some((h) => flagged?.has(h.ts));

  return (
    <div className="hours">
      <div className="hours-plot" role="img" aria-label={label} style={{ height }}>
        {hourly.map((h, i) => {
          const isFlagged = flagged?.has(h.ts) ?? false;
          const total = totalCounts(h.counts);
          const current = i === hourly.length - 1;
          const tip = h.missing
            ? `${hhmm(h.ts)} · no data`
            : `${hhmm(h.ts)} · ${num(total)} passes${current ? " (current hour)" : ""}${isFlagged ? " · to review" : ""}`;
          return (
            <div
              key={h.ts}
              title={tip}
              className={["hour", h.missing ? "missing" : "", isFlagged ? "flag" : "", current ? "now" : ""]
                .filter(Boolean)
                .join(" ")}
            >
              {h.missing ? null : (
                <div className="hour-stack" style={{ height: `${(total / max) * 100}%` }}>
                  {CLASS_ORDER.map((c) =>
                    h.counts[c] > 0 ? (
                      <span key={c} style={{ flexGrow: h.counts[c], background: CLASS_PEN[c] }} />
                    ) : null,
                  )}
                </div>
              )}
            </div>
          );
        })}
      </div>
      <div className="hours-axis" aria-hidden="true">
        {hourly.map((h, i) => (
          <span key={h.ts}>
            {i === hourly.length - 1
              ? "now"
              : i % 3 === 0
                ? String(new Date(h.ts).getHours()).padStart(2, "0")
                : ""}
          </span>
        ))}
      </div>
      <div className="hours-key">
        <span>
          <i className="key-now" aria-hidden="true" /> current hour, still partial
        </span>
        {hasFlag ? (
          <span>
            <i className="key-flag" aria-hidden="true" /> unusual hour
          </span>
        ) : null}
        {missing > 0 ? (
          <span>
            <i className="key-missing" aria-hidden="true" /> no data ({missing} h)
          </span>
        ) : null}
      </div>

      <div className="sr">
      <table>
        <caption>{label}</caption>
        <thead>
          <tr>
            <th scope="col">Hour</th>
            {CLASS_ORDER.map((c) => (
              <th scope="col" key={c}>
                {CLASS_LABEL[c]}
              </th>
            ))}
            <th scope="col">Total</th>
          </tr>
        </thead>
        <tbody>
          {hourly.map((h, i) => (
            <tr key={h.ts}>
              <th scope="row">
                {hhmm(h.ts)}
                {i === hourly.length - 1 ? " (in progress)" : ""}
                {flagged?.has(h.ts) ? ", to review" : ""}
              </th>
              {h.missing ? (
                <td colSpan={CLASS_ORDER.length + 1}>no data</td>
              ) : (
                <>
                  {CLASS_ORDER.map((c) => (
                    <td key={c}>{num(h.counts[c])}</td>
                  ))}
                  <td>{num(totalCounts(h.counts))}</td>
                </>
              )}
            </tr>
          ))}
        </tbody>
      </table>
      </div>
    </div>
  );
}
