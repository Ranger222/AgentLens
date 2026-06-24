// Pure helpers — the testable heart of the waterfall.

import type { SpanNode } from "./types";

export interface FlatRow {
  span: SpanNode;
  depth: number;
  hasChildren: boolean;
}

/** Pre-order flatten of the span tree, skipping subtrees whose id is collapsed. */
export function flatten(tree: SpanNode[], collapsed: Set<string>): FlatRow[] {
  const rows: FlatRow[] = [];
  const walk = (nodes: SpanNode[], depth: number): void => {
    for (const span of nodes) {
      const hasChildren = (span.children?.length ?? 0) > 0;
      rows.push({ span, depth, hasChildren });
      if (hasChildren && !collapsed.has(span.span_id)) {
        walk(span.children, depth + 1);
      }
    }
  };
  walk(tree, 0);
  return rows;
}

/** All span ids that have children — used by "expand/collapse all". */
export function collapsibleIds(tree: SpanNode[]): string[] {
  const ids: string[] = [];
  const walk = (nodes: SpanNode[]): void => {
    for (const s of nodes) {
      if ((s.children?.length ?? 0) > 0) {
        ids.push(s.span_id);
        walk(s.children);
      }
    }
  };
  walk(tree);
  return ids;
}

export interface TimeWindow {
  start: number;
  end: number;
}

/** Run duration in seconds, guarded so an instantaneous run never divides by zero. */
export function runDuration(w: TimeWindow): number {
  return Math.max(w.end - w.start, 1e-9);
}

export function clampPct(v: number): number {
  if (Number.isNaN(v)) return 0;
  // Math.min/max collapse ±Infinity to the [0,100] bounds (huge width → 100).
  return Math.max(0, Math.min(100, v));
}

const MIN_BAR_PCT = 0.6; // keep sub-millisecond spans clickable

/**
 * Position a span's bar as % of the run window. `left` from start offset,
 * `width` from duration — never by depth (that's the classic homemade bug).
 * Times are epoch seconds.
 */
export function barGeometry(span: SpanNode, w: TimeWindow): { left: number; width: number } {
  const dur = runDuration(w);
  const left = clampPct(((span.start_time - w.start) / dur) * 100);
  const end = span.end_time ?? w.end; // running span extends to the window end
  const rawWidth = ((end - span.start_time) / dur) * 100;
  const width = Math.max(clampPct(rawWidth), MIN_BAR_PCT);
  const clampedLeft = Math.min(left, 100 - MIN_BAR_PCT);
  return { left: clampedLeft, width: Math.min(width, 100 - clampedLeft) };
}

export function formatDuration(ms: number | null | undefined): string {
  if (ms == null) return "—";
  if (ms < 1) return `${Math.round(ms * 1000)}µs`;
  if (ms < 1000) return `${ms < 10 ? ms.toFixed(1) : Math.round(ms)}ms`;
  return `${(ms / 1000).toFixed(2)}s`;
}

export function formatTokens(n: number | null | undefined): string {
  return n == null ? "—" : n.toLocaleString();
}

export function formatClock(epochSec: number): string {
  return new Date(epochSec * 1000).toLocaleString();
}

/** Human "3m ago" style relative time. */
export function relTime(epochSec: number, now: number = Date.now() / 1000): string {
  const s = Math.max(0, now - epochSec);
  if (s < 60) return `${Math.floor(s)}s ago`;
  if (s < 3600) return `${Math.floor(s / 60)}m ago`;
  if (s < 86400) return `${Math.floor(s / 3600)}h ago`;
  return `${Math.floor(s / 86400)}d ago`;
}

/** CSS variable name for a span type's accent colour. */
export function typeColorVar(type: string): string {
  switch (type) {
    case "llm_call":
      return "var(--span-llm)";
    case "tool_call":
      return "var(--span-tool)";
    case "agent_step":
      return "var(--span-agent)";
    case "retrieval":
      return "var(--span-retrieval)";
    case "chain":
      return "var(--span-chain)";
    default:
      return "var(--span-custom)";
  }
}

export function prettyType(type: string): string {
  return type.replace(/_/g, " ");
}
