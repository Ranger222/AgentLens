import { describe, expect, it } from "vitest";
import type { SpanNode } from "../types";
import {
  barGeometry,
  clampPct,
  collapsibleIds,
  flatten,
  formatDuration,
  runDuration,
} from "../util";

function span(partial: Partial<SpanNode> & { span_id: string }): SpanNode {
  return {
    run_id: "r",
    parent_id: null,
    name: partial.span_id,
    type: "agent_step",
    start_time: 0,
    end_time: 1,
    duration_ms: 1000,
    status: "ok",
    input: null,
    output: null,
    error: null,
    usage: null,
    model: null,
    metadata: {},
    seq: 0,
    children: [],
    ...partial,
  };
}

describe("flatten", () => {
  const tree: SpanNode[] = [
    span({
      span_id: "root",
      children: [
        span({ span_id: "a", children: [span({ span_id: "a1" })] }),
        span({ span_id: "b" }),
      ],
    }),
  ];

  it("pre-order walks the whole tree when nothing is collapsed", () => {
    const rows = flatten(tree, new Set());
    expect(rows.map((r) => r.span.span_id)).toEqual(["root", "a", "a1", "b"]);
    expect(rows.map((r) => r.depth)).toEqual([0, 1, 2, 1]);
  });

  it("skips collapsed subtrees but keeps the collapsed node itself", () => {
    const rows = flatten(tree, new Set(["a"]));
    expect(rows.map((r) => r.span.span_id)).toEqual(["root", "a", "b"]);
  });

  it("marks rows that have children", () => {
    const rows = flatten(tree, new Set());
    const byId = Object.fromEntries(rows.map((r) => [r.span.span_id, r.hasChildren]));
    expect(byId).toEqual({ root: true, a: true, a1: false, b: false });
  });
});

describe("collapsibleIds", () => {
  it("returns only ids that have children", () => {
    const tree = [span({ span_id: "root", children: [span({ span_id: "leaf" })] })];
    expect(collapsibleIds(tree)).toEqual(["root"]);
  });
});

describe("runDuration / clampPct", () => {
  it("guards a zero-length window against divide-by-zero", () => {
    expect(runDuration({ start: 5, end: 5 })).toBeGreaterThan(0);
  });
  it("clamps into [0,100] and handles NaN/Infinity", () => {
    expect(clampPct(-10)).toBe(0);
    expect(clampPct(150)).toBe(100);
    expect(clampPct(NaN)).toBe(0);
    expect(clampPct(Infinity)).toBe(100);
  });
});

describe("barGeometry", () => {
  const window = { start: 100, end: 110 }; // 10s run

  it("positions a bar by start offset and duration (not depth)", () => {
    const s = span({ span_id: "x", start_time: 102, end_time: 107, duration_ms: 5000 });
    const { left, width } = barGeometry(s, window);
    expect(left).toBeCloseTo(20, 5); // (102-100)/10 = 20%
    expect(width).toBeCloseTo(50, 5); // (107-102)/10 = 50%
  });

  it("clamps a tiny span to a minimum visible width", () => {
    const s = span({ span_id: "tiny", start_time: 105, end_time: 105.0001, duration_ms: 0.1 });
    const { width } = barGeometry(s, window);
    expect(width).toBeGreaterThanOrEqual(0.6);
  });

  it("extends a still-running span to the window end", () => {
    const s = span({ span_id: "live", start_time: 105, end_time: null, duration_ms: null });
    const { left, width } = barGeometry(s, window);
    expect(left).toBeCloseTo(50, 5);
    expect(width).toBeCloseTo(50, 5);
  });

  it("never produces NaN when the window has zero length", () => {
    const s = span({ span_id: "z", start_time: 5, end_time: 5, duration_ms: 0 });
    const { left, width } = barGeometry(s, { start: 5, end: 5 });
    expect(Number.isNaN(left)).toBe(false);
    expect(Number.isNaN(width)).toBe(false);
  });
});

describe("formatDuration", () => {
  it("formats µs / ms / s", () => {
    expect(formatDuration(null)).toBe("—");
    expect(formatDuration(0.25)).toBe("250µs");
    expect(formatDuration(5.4)).toBe("5.4ms");
    expect(formatDuration(120)).toBe("120ms");
    expect(formatDuration(2500)).toBe("2.50s");
  });
});
