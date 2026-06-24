// 1:1 port of the Python dataclasses serialized by the FastAPI backend.

export type SpanStatus = "running" | "ok" | "error";

export interface TokenUsage {
  input_tokens: number | null;
  output_tokens: number | null;
  total_tokens: number | null;
}

export interface ErrorInfo {
  type: string;
  message: string;
  traceback: string | null;
}

export interface SpanNode {
  span_id: string;
  run_id: string;
  parent_id: string | null;
  name: string;
  type: string;
  start_time: number; // epoch seconds
  end_time: number | null;
  duration_ms: number | null;
  status: SpanStatus;
  input: unknown;
  output: unknown;
  error: ErrorInfo | null;
  usage: TokenUsage | null;
  model: string | null;
  metadata: Record<string, unknown>;
  seq: number;
  children: SpanNode[];
}

export interface Run {
  run_id: string;
  name: string | null;
  start_time: number;
  end_time: number | null;
  duration_ms: number | null;
  status: SpanStatus;
  metadata: Record<string, unknown>;
}

export interface RunSummary {
  run_id: string;
  name: string | null;
  start_time: number;
  end_time: number | null;
  duration_ms: number | null;
  status: SpanStatus;
  span_count: number;
  error_count: number;
  total_tokens: number | null;
  models: Record<string, number>;
  metadata: Record<string, unknown>;
}

export interface RunListResponse {
  runs: RunSummary[];
  total: number;
  limit: number;
  offset: number;
}

export interface RunDetail {
  run: Run;
  window: { start: number; end: number };
  spans: SpanNode[];
  tree: SpanNode[];
}
