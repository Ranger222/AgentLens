import type { SpanNode } from "../types";
import { formatDuration, formatTokens, prettyType, typeColorVar } from "../util";
import { JsonView } from "./JsonView";
import { StatusBadge } from "./StatusBadge";

export function SpanDetailPanel({ span }: { span: SpanNode | null }) {
  if (!span) {
    return (
      <aside className="detail">
        <div className="empty">Select a span to inspect its input, output, tokens & errors.</div>
      </aside>
    );
  }

  const hasUsage = span.usage && (span.usage.total_tokens != null || span.usage.input_tokens != null);
  const hasMeta = span.metadata && Object.keys(span.metadata).length > 0;

  return (
    <aside className="detail">
      <h3>{span.name}</h3>
      <div style={{ display: "flex", gap: 8, alignItems: "center", marginTop: 6 }}>
        <span className="badge" style={{ color: typeColorVar(span.type), borderColor: "var(--border)" }}>
          {prettyType(span.type)}
        </span>
        <StatusBadge status={span.status} />
      </div>

      {/* Error first & prominent when present */}
      {span.error && (
        <div className="section">
          <div className="label">Error</div>
          <div className="error-box">
            <div className="etype">{span.error.type}</div>
            <div>{span.error.message}</div>
            {span.error.traceback && <pre>{span.error.traceback}</pre>}
          </div>
        </div>
      )}

      <div className="section">
        <div className="label">Timing</div>
        <div className="kv">
          <span className="k">Duration</span>
          <span className="v">{formatDuration(span.duration_ms)}</span>
          {span.model && (
            <>
              <span className="k">Model</span>
              <span className="v">{span.model}</span>
            </>
          )}
          <span className="k">Span ID</span>
          <span className="v run-id">{span.span_id}</span>
        </div>
      </div>

      {hasUsage && (
        <div className="section">
          <div className="label">Tokens</div>
          <div className="kv">
            <span className="k">Input</span>
            <span className="v">{formatTokens(span.usage!.input_tokens)}</span>
            <span className="k">Output</span>
            <span className="v">{formatTokens(span.usage!.output_tokens)}</span>
            <span className="k">Total</span>
            <span className="v">{formatTokens(span.usage!.total_tokens)}</span>
          </div>
        </div>
      )}

      <div className="section">
        <div className="label">Input</div>
        <JsonView value={span.input} />
      </div>

      <div className="section">
        <div className="label">Output</div>
        <JsonView value={span.output} />
      </div>

      {hasMeta && (
        <div className="section">
          <div className="label">Metadata</div>
          <JsonView value={span.metadata} />
        </div>
      )}
    </aside>
  );
}
