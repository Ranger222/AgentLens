import type { SpanNode } from "../types";
import type { TimeWindow } from "../util";
import { barGeometry, formatDuration, typeColorVar } from "../util";
import { TypeDot } from "./TypeDot";

interface Props {
  span: SpanNode;
  depth: number;
  hasChildren: boolean;
  collapsed: boolean;
  selected: boolean;
  window: TimeWindow;
  onToggle: () => void;
  onSelect: () => void;
}

export function SpanRow({
  span,
  depth,
  hasChildren,
  collapsed,
  selected,
  window,
  onToggle,
  onSelect,
}: Props) {
  const { left, width } = barGeometry(span, window);
  const isError = span.status === "error";
  const isRunning = span.status === "running";
  const barClass = isError ? "bar error" : isRunning ? "bar running" : "bar";

  return (
    <div
      className={`span-row${selected ? " selected" : ""}${isError ? " is-error" : ""}`}
      role="treeitem"
      aria-selected={selected}
      onClick={onSelect}
    >
      <div className="gutter" style={{ paddingLeft: 8 + depth * 16 }}>
        {hasChildren ? (
          <button
            className="caret"
            onClick={(e) => {
              e.stopPropagation();
              onToggle();
            }}
            aria-label={collapsed ? "Expand" : "Collapse"}
          >
            {collapsed ? "▸" : "▾"}
          </button>
        ) : (
          <span className="caret placeholder">▸</span>
        )}
        <TypeDot type={span.type} />
        <span className="span-name" title={span.name}>
          {span.name}
        </span>
        {span.model && <span className="span-model">{span.model}</span>}
      </div>
      <div className="track">
        <div
          className={barClass}
          style={{
            left: `${left}%`,
            width: `${width}%`,
            background: isError ? undefined : typeColorVar(span.type),
          }}
        >
          <span className="bar-label">{formatDuration(span.duration_ms)}</span>
        </div>
      </div>
    </div>
  );
}
