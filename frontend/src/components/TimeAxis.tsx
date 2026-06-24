import type { TimeWindow } from "../util";
import { formatDuration, runDuration } from "../util";

// A simple 0/25/50/75/100% tick ruler aligned with the waterfall track.
export function TimeAxis({ window }: { window: TimeWindow }) {
  const totalMs = runDuration(window) * 1000;
  const ticks = [0, 0.25, 0.5, 0.75];
  return (
    <div className="timeaxis">
      {ticks.map((f) => (
        <div className="tick" key={f} style={{ left: `${f * 100}%` }}>
          {formatDuration(totalMs * f)}
        </div>
      ))}
      <div className="tick" style={{ left: "100%", transform: "translateX(-100%)" }}>
        {formatDuration(totalMs)}
      </div>
    </div>
  );
}
