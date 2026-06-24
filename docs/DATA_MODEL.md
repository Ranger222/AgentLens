# Data model & API

## Run

A **run** groups all spans from one traced execution (≈ an OpenTelemetry trace).

| Field | Type | Notes |
|---|---|---|
| `run_id` | `str` | 32 hex chars (16 CSPRNG bytes). |
| `name` | `str \| None` | Defaults to the root span's name. |
| `start_time` | `float` | Epoch seconds. |
| `end_time` | `float \| None` | `None` while running. |
| `status` | `str` | `running` \| `ok` \| `error` (error if **any** span errored). |
| `metadata` | `dict` | User free-form. |

## Span

A **span** is one unit of work; spans nest via `parent_id` to form a tree.

| Field | Type | Notes |
|---|---|---|
| `span_id` | `str` | 16 hex chars (8 CSPRNG bytes). |
| `run_id` | `str` | Denormalized on every span → one indexed query loads a run. |
| `parent_id` | `str \| None` | `None` = run root. |
| `name` | `str` | `@trace` → `func.__qualname__`; `span()` → required arg. |
| `type` | `str` | Open string; see below. |
| `start_time` / `end_time` | `float` / `float \| None` | Epoch seconds. `end = start + monotonic Δ`. |
| `duration_ms` | `float \| None` | Derived (`(end-start)*1000`), never negative. |
| `status` | `str` | `running` \| `ok` \| `error`. |
| `input` / `output` | `Any` | Safe-serialized; secrets redacted; truncated at 64 KiB. |
| `error` | `ErrorInfo \| None` | `{type, message, traceback}`. |
| `usage` | `TokenUsage \| None` | `{input_tokens, output_tokens, total_tokens}`. |
| `model` | `str \| None` | For `llm_call` spans. |
| `metadata` | `dict` | User free-form + instrumentation hints (e.g. `provider`). |
| `seq` | `int` | Per-run insertion order; sibling tiebreaker for equal `start_time`. |

### Span types (`SpanType`)
`llm_call`, `tool_call`, `agent_step` (default), `chain`, `retrieval`, `custom`.
Stored as free TEXT — a custom string is never rejected. Loosely maps to
OpenInference `openinference.span.kind` / OTel `gen_ai.operation.name` for a
future OTLP exporter.

### Span statuses (`SpanStatus`)
`running` (created, not ended), `ok` (ended cleanly), `error` (ended via raised
exception). `running` is a deliberate, documented divergence from OTel's `UNSET`
— it carries more information for a local dashboard that may render in-flight
runs and for crash-truncated spans.

## SQLite schema

```sql
PRAGMA journal_mode = WAL;     -- concurrent dashboard reader + SDK writer
PRAGMA synchronous  = NORMAL;
PRAGMA foreign_keys = ON;

CREATE TABLE runs (
    run_id TEXT PRIMARY KEY, name TEXT, start_time REAL NOT NULL,
    end_time REAL, status TEXT NOT NULL, metadata TEXT, created_at REAL NOT NULL
);
CREATE TABLE spans (
    span_id TEXT PRIMARY KEY, run_id TEXT NOT NULL, parent_id TEXT,
    name TEXT NOT NULL, type TEXT NOT NULL, start_time REAL NOT NULL, end_time REAL,
    status TEXT NOT NULL, input TEXT, output TEXT, error TEXT, usage TEXT,
    total_tokens INTEGER,  -- flattened from usage for cheap SUM() rollups
    model TEXT, metadata TEXT, seq INTEGER NOT NULL,
    FOREIGN KEY (run_id) REFERENCES runs(run_id) ON DELETE CASCADE
);
CREATE INDEX idx_spans_run       ON spans(run_id);
CREATE INDEX idx_spans_parent    ON spans(parent_id);
CREATE INDEX idx_spans_run_order ON spans(run_id, start_time, seq);
CREATE INDEX idx_runs_start      ON runs(start_time DESC);
```

JSON-valued columns (`input`, `output`, `error`, `usage`, `metadata`) store the
serialized text and are parsed back on read.

## HTTP API

All JSON, all under `/api` (registered before the static mount so the SPA never
shadows them). Read-only except `DELETE`.

| Method | Route | Returns |
|---|---|---|
| `GET` | `/api/health` | `{status, version, db_path, db_exists}` |
| `GET` | `/api/runs?limit=&offset=` | `{runs: RunSummary[], total, limit, offset}` newest-first, with `span_count`, `error_count`, `total_tokens`, `models` breakdown |
| `GET` | `/api/runs/{run_id}` | `{run, window:{start,end}, spans: Span[] (flat), tree: SpanNode[] (nested)}` |
| `GET` | `/api/runs/{run_id}/spans/{span_id}` | a single `Span` (detail) |
| `DELETE` | `/api/runs/{run_id}` | `{deleted: bool, run_id}` |

The **tree** is assembled server-side in one O(n) pass from the flat,
`(start_time, seq)`-ordered span list. Orphan spans (parent missing) are kept as
roots so nothing is ever dropped.

## Frontend waterfall

The flat tree is rendered as a list of rows; collapse state is a `Set` of span
ids. For each visible span:

```
left  = (span.start_time - window.start) / runDuration * 100%   // clamped [0,100]
width = (span.end - span.start)          / runDuration * 100%   // min 0.6% so tiny spans stay clickable
```

Indentation (`depth * 16px`) expresses hierarchy; the bar's horizontal position
expresses time. `runDuration` is guarded against zero. See
`frontend/src/util.ts` (unit-tested) for the exact math.
