import { useRuns } from "../api";
import type { RunSummary } from "../types";
import { formatDuration, formatTokens, relTime } from "../util";
import { StatusBadge } from "./StatusBadge";

export function RunList({ onSelect }: { onSelect: (runId: string) => void }) {
  const { data, loading, error, reload } = useRuns();

  if (loading) {
    return (
      <div className="center">
        <div className="spinner" />
        <div>Loading runs…</div>
      </div>
    );
  }
  if (error) {
    return (
      <div className="center">
        <div className="error-text">Failed to load runs: {error}</div>
        <button className="btn" onClick={reload}>
          Retry
        </button>
      </div>
    );
  }

  const runs = data?.runs ?? [];
  if (runs.length === 0) {
    return (
      <div className="center empty-state">
        <div style={{ fontSize: 32 }}>🔍</div>
        <h2>No runs yet</h2>
        <p className="muted">
          Generate a sample trace with <code>lenstrace demo</code>, or instrument your
          agent with <code>@trace</code> and run it.
        </p>
        <button className="btn" onClick={reload}>
          Refresh
        </button>
      </div>
    );
  }

  return (
    <div className="runlist">
      <h1>Runs</h1>
      <p className="sub">
        {data?.total ?? runs.length} run{(data?.total ?? 0) === 1 ? "" : "s"} · click one to
        open its timeline
      </p>
      <table className="run-table">
        <thead>
          <tr>
            <th>Run</th>
            <th>Status</th>
            <th>Started</th>
            <th>Duration</th>
            <th className="num">Spans</th>
            <th className="num">Errors</th>
            <th className="num">Tokens</th>
            <th>Models</th>
          </tr>
        </thead>
        <tbody>
          {runs.map((r) => (
            <RunRow key={r.run_id} run={r} onSelect={onSelect} />
          ))}
        </tbody>
      </table>
    </div>
  );
}

function RunRow({ run, onSelect }: { run: RunSummary; onSelect: (id: string) => void }) {
  return (
    <tr onClick={() => onSelect(run.run_id)}>
      <td>
        <div className="run-name">{run.name || "(unnamed run)"}</div>
        <div className="run-id">{run.run_id.slice(0, 12)}</div>
      </td>
      <td>
        <StatusBadge status={run.status} />
      </td>
      <td className="muted">{relTime(run.start_time)}</td>
      <td className="num">{formatDuration(run.duration_ms)}</td>
      <td className="num">{run.span_count}</td>
      <td className="num" style={{ color: run.error_count ? "var(--err)" : undefined }}>
        {run.error_count || ""}
      </td>
      <td className="num">{formatTokens(run.total_tokens)}</td>
      <td>
        <div className="model-chips">
          {Object.entries(run.models).map(([m, c]) => (
            <span className="model-chip" key={m}>
              {m}
              {c > 1 ? ` ×${c}` : ""}
            </span>
          ))}
        </div>
      </td>
    </tr>
  );
}
