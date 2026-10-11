import type { Counts, HourBucket } from "../data/types";
import { totalCounts } from "../data/types";
import { CLASS_LABEL, CLASS_ORDER, CLASS_PEN } from "../lib/classes";
import { hhmm, num, share } from "../lib/format";
import { HourField } from "./HourField";

interface NetworkChartProps {
  hourly: HourBucket[];
  flagged: Set<number>;
  peakTs: number | null;
  totals: Counts;
}

/** All intersections summed, hour by hour, with the class legend. */
export function NetworkChart({ hourly, flagged, peakTs, totals }: NetworkChartProps) {
  const total = totalCounts(totals);
  const peak = hourly.find((h) => h.ts === peakTs);
  return (
    <section className="panel network" aria-labelledby="network-title">
      <div className="block-head">
        <h2 id="network-title">Whole corridor, hour by hour</h2>
        <span>{peak ? `busiest at ${hhmm(peak.ts)}` : "no data"}</span>
      </div>
      <HourField
        hourly={hourly}
        flagged={flagged}
        height={64}
        label={`Passes at all intersections in the last 24 hours: ${num(total)} in total`}
      />
      <ul className="legend" aria-label="Passes by type, all intersections">
        {CLASS_ORDER.map((c) => (
          <li key={c}>
            <span className="swatch" style={{ background: CLASS_PEN[c] }} aria-hidden="true" />
            <span>{CLASS_LABEL[c]}</span>
            <b>{num(totals[c])}</b>
            <small>{share(totals[c], total)}</small>
          </li>
        ))}
      </ul>
    </section>
  );
}
