import type { SpanStatus } from "../types";

const LABEL: Record<SpanStatus, string> = {
  ok: "ok",
  error: "error",
  running: "running",
};

export function StatusBadge({ status }: { status: SpanStatus }) {
  return (
    <span className={`badge ${status}`}>
      {status === "error" ? "⚠ " : ""}
      {LABEL[status] ?? status}
    </span>
  );
}
