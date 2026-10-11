import type { NodeView } from "../lib/view";
import { nextAfter, openAnomalies } from "../lib/view";
import { elapsed, num, perMinute } from "../lib/format";

interface SummaryBarProps {
  views: NodeView[];
  networkTotal: number;
  networkRate: number;
  now: number;
  selectedId: string | null;
  onSelect: (id: string) => void;
}

/**
 * The answer to the first question, in three tiles: is the network working?
 * how much traffic is there? is there anything to do? The first and last tiles
 * lead straight to the intersection that needs a look, and move on to the next
 * one at each click.
 */
export function SummaryBar({ views, networkTotal, networkRate, now, selectedId, onSelect }: SummaryBarProps) {
  const offline = views.filter((v) => !v.status.online);
  const online = views.length - offline.length;
  const withChecks = views.filter((v) => v.status.online && openAnomalies(v).length > 0);
  const openTotal = withChecks.reduce((n, v) => n + openAnomalies(v).length, 0);
  const offlineNext = nextAfter(offline, selectedId);
  const checksNext = nextAfter(withChecks, selectedId);
  const frozenTotal = offline.reduce((n, v) => n + v.total, 0);
  const offlineOnSelected = offline.some((v) => v.node.id === selectedId);
  const checksOnSelected = withChecks.some((v) => v.node.id === selectedId);

  return (
    <section className="summary" aria-label="Network summary">
      {offline.length === 0 ? (
        <div className="sum ok">
          <span className="sum-k">Sensors</span>
          <span className="sum-v">All active</span>
          <span className="sum-s">
            {online} of {views.length} responding
          </span>
        </div>
      ) : (
        <button type="button" className="sum off" onClick={() => offlineNext && onSelect(offlineNext.node.id)}>
          <span className="sum-k">Sensors</span>
          <span className="sum-v">
            {offline.length === 1 ? "1 not responding" : `${offline.length} not responding`}
          </span>
          <span className="sum-s">
            {offlineNext?.node.name}, for {elapsed(offlineNext?.status.lastBeat ?? now, now)}
            {" · "}
            {online} of {views.length} active
            {offline.length > 1 || !offlineOnSelected ? <span className="nw"> · open →</span> : null}
          </span>
        </button>
      )}

      <div className="sum">
        <span className="sum-k">Passes, last 24 hours</span>
        <span className="sum-v">{num(networkTotal)}</span>
        <span className="sum-s">
          {perMinute(networkRate)}/min right now
          {frozenTotal > 0
            ? `, includes ${num(frozenTotal)} frozen at ${offline.length === 1 ? offline[0].node.name : `${offline.length} silent sensors`}`
            : ", across the whole street"}
        </span>
      </div>

      {openTotal === 0 ? (
        <div className="sum ok">
          <span className="sum-k">To review</span>
          <span className="sum-v">Nothing</span>
          <span className="sum-s">no counts far from the usual</span>
        </div>
      ) : (
        <button type="button" className="sum warn" onClick={() => checksNext && onSelect(checksNext.node.id)}>
          <span className="sum-k">To review</span>
          <span className="sum-v">
            {openTotal === 1 ? "1 unusual hour" : `${openTotal} unusual hours`}
          </span>
          <span className="sum-s">
            far from the usual, on {withChecks.length === 1 ? "1 intersection" : `${withChecks.length} intersections`}
            <span className="nw">
              {" · "}
              {withChecks.length > 1 && checksOnSelected ? "go to next" : checksOnSelected ? "shown" : "open"} →
            </span>
          </span>
        </button>
      )}
    </section>
  );
}
