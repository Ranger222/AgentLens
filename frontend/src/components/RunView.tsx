import { useMemo, useState } from "react";
import { useRun } from "../api";
import type { SpanNode } from "../types";
import { collapsibleIds, flatten, formatDuration } from "../util";
import { SpanDetailPanel } from "./SpanDetailPanel";
import { SpanRow } from "./SpanRow";
import { StatusBadge } from "./StatusBadge";
import { TimeAxis } from "./TimeAxis";

const GUTTER_PX = 320;

export function RunView({ runId, onBack }: { runId: string; onBack: () => void }) {
  const { data, loading, error } = useRun(runId);
  const [collapsed, setCollapsed] = useState<Set<string>>(new Set());
  const [selectedId, setSelectedId] = useState<string | null>(null);

  const window = data?.window ?? { start: 0, end: 1 };
  const rows = useMemo(
    () => (data ? flatten(data.tree, collapsed) : []),
    [data, collapsed]
  );
  const selected: SpanNode | null = useMemo(() => {
    if (!data || !selectedId) return null;
    return data.spans.find((s) => s.span_id === selectedId) ?? null;
  }, [data, selectedId]);

  const toggle = (id: string) => {
    setCollapsed((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };
  const collapseAll = () => data && setCollapsed(new Set(collapsibleIds(data.tree)));
  const expandAll = () => setCollapsed(new Set());

  if (loading) {
    return (
      <div className="center">
        <div className="spinner" />
        <div>Loading run…</div>
      </div>
    );
  }
  if (error || !data) {
    return (
      <div className="center">
        <div className="error-text">Failed to load run: {error ?? "not found"}</div>
        <button className="btn" onClick={onBack}>
          ← Back to runs
        </button>
      </div>
    );
  }

  return (
    <div className="runview">
      <div className="runview-header">
        <span className="runview-title">{data.run.name || "(unnamed run)"}</span>
        <StatusBadge status={data.run.status} />
        <span className="muted">{formatDuration(data.run.duration_ms)}</span>
        <span className="muted run-id">{data.run.run_id.slice(0, 16)}</span>
      </div>
      <div className="runview-body">
        <div className="waterfall" style={{ ["--gutter" as string]: `${GUTTER_PX}px` }}>
          <div className="toolbar">
            <button className="btn ghost" onClick={expandAll}>
              Expand all
            </button>
            <button className="btn ghost" onClick={collapseAll}>
              Collapse all
            </button>
            <span className="spacer" style={{ flex: 1 }} />
            <span className="muted">{rows.length} spans</span>
          </div>
          <TimeAxis window={window} />
          <div role="tree">
            {rows.map(({ span, depth, hasChildren }) => (
              <SpanRow
                key={span.span_id}
                span={span}
                depth={depth}
                hasChildren={hasChildren}
                collapsed={collapsed.has(span.span_id)}
                selected={span.span_id === selectedId}
                window={window}
                onToggle={() => toggle(span.span_id)}
                onSelect={() => setSelectedId(span.span_id)}
              />
            ))}
          </div>
        </div>
        <SpanDetailPanel span={selected} />
      </div>
    </div>
  );
}
