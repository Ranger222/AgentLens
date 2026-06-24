import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { SpanDetailPanel } from "../components/SpanDetailPanel";
import { StatusBadge } from "../components/StatusBadge";
import type { SpanNode } from "../types";

function makeSpan(over: Partial<SpanNode>): SpanNode {
  return {
    span_id: "s1",
    run_id: "r1",
    parent_id: null,
    name: "calculator",
    type: "tool_call",
    start_time: 0,
    end_time: 1,
    duration_ms: 12.5,
    status: "ok",
    input: { expr: "1/0" },
    output: null,
    error: null,
    usage: null,
    model: null,
    metadata: {},
    seq: 0,
    children: [],
    ...over,
  };
}

describe("StatusBadge", () => {
  it("renders the status label", () => {
    render(<StatusBadge status="error" />);
    expect(screen.getByText(/error/)).toBeInTheDocument();
  });
});

describe("SpanDetailPanel", () => {
  it("prompts to select a span when none is given", () => {
    render(<SpanDetailPanel span={null} />);
    expect(screen.getByText(/select a span/i)).toBeInTheDocument();
  });

  it("shows the error block prominently for a failed span", () => {
    const span = makeSpan({
      status: "error",
      error: { type: "ZeroDivisionError", message: "division by zero", traceback: "Traceback..." },
    });
    render(<SpanDetailPanel span={span} />);
    expect(screen.getByText("ZeroDivisionError")).toBeInTheDocument();
    expect(screen.getByText("division by zero")).toBeInTheDocument();
  });

  it("renders token usage when present", () => {
    const span = makeSpan({
      type: "llm_call",
      model: "gpt-4o",
      usage: { input_tokens: 10, output_tokens: 5, total_tokens: 15 },
    });
    render(<SpanDetailPanel span={span} />);
    expect(screen.getByText("Tokens")).toBeInTheDocument();
    expect(screen.getByText("15")).toBeInTheDocument();
  });
});
