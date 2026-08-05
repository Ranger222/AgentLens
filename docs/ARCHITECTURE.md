# Architecture

LensTrace is three cooperating pieces around one SQLite file:

```
   your Python agent                          your browser
┌────────────────────┐                   ┌────────────────────┐
│  @trace / span()   │                   │  React dashboard    │
│  instrument_openai │                   │  (waterfall + tree) │
└─────────┬──────────┘                   └──────────┬─────────┘
          │ writes spans                            │ GET /api/*
          ▼                                          ▼
┌────────────────────┐    reads (WAL)    ┌────────────────────┐
│  SDK core (stdlib) │◄─────────────────►│  FastAPI backend    │
│  Tracer + Storage  │   lenstrace.db    │  (read-only conn)   │
└────────────────────┘                   └────────────────────┘
            \________________  SQLite  _______________/
```

The SDK **writes**, the dashboard **reads**, and SQLite's WAL mode makes that
cross-process sharing safe with zero coordination. No daemon, no broker, no
network in the hot path.

## Components

### 1. SDK core — `lenstrace` (standard library only)
Importing `lenstrace` pulls in **only the Python standard library**
(`contextvars`, `sqlite3`, `dataclasses`, `threading`, `secrets`, …). FastAPI /
uvicorn are imported lazily inside `lenstrace.server`, and `openai` / `anthropic`
only inside their instrumentation modules — so adding tracing to an agent never
forces heavy or unwanted dependencies.

| Module | Responsibility |
|---|---|
| `models.py` | `Span`, `Run`, `RunSummary`, `TokenUsage`, `ErrorInfo`; open `SpanType`, `SpanStatus`. |
| `ids.py` | CSPRNG hex ids (OTel-shaped: 16-byte run, 8-byte span). |
| `serialization.py` | Defensive `to_jsonable` (pydantic/dataclass/bytes aware), secret redaction, truncation. |
| `context.py` | `contextvars` holding the current run/span; guarded reset across async/thread boundaries. |
| `tracer.py` | Run/span lifecycle, implicit + explicit runs, per-run error rollup, persistence. Never raises into user code. |
| `decorators.py` | `@trace` for sync / async / generator / async-generator functions. |
| `spans.py` | `span()` and `run()` context managers; manual `start_span`/`end_span`. |
| `concurrency.py` | `TracedThreadPoolExecutor` (copies context into workers). |
| `storage/` | `Storage` ABC + `SQLiteStorage` (WAL, indexes, rollups). |
| `instrument/` | Idempotent OpenAI & Anthropic auto-instrumentation. |

### 2. Backend — `lenstrace.server` (FastAPI)
A thin, **read-only** JSON API over the trace DB plus static serving of the
built React app. Opens its own SQLite connection on the same file the SDK writes
to. See [DATA_MODEL.md](DATA_MODEL.md) for the routes.

### 3. Frontend — `frontend/` (React + Vite + TypeScript)
A hand-rolled, dependency-light dashboard. The waterfall is one CSS trick
(absolute bars positioned by start-offset % and width by duration %); hierarchy
is expressed by gutter indentation only. See the frontend section of
[DATA_MODEL.md](DATA_MODEL.md) and the components under `frontend/src/`.

## How nesting works (the core idea)

A module-level `contextvars.ContextVar` holds the "current span". Opening a span
snapshots that var as its `parent_id`, sets itself current, and restores the
previous value on close. Because `contextvars` are copied per `asyncio.Task` and
(via `TracedThreadPoolExecutor`) per worker thread, **parent/child is inferred
automatically** — users never thread a parent id through their call signatures.

The first span opened when no run is active auto-creates the run and "owns" it;
closing that span finalizes the run. `run()` lets you group several top-level
spans explicitly.

## Reliability principles

1. **Never crash the user's app.** Every storage call is wrapped; a failing
   backend degrades to "missing span", never a raised exception. (`tracer._safe`)
2. **Never reject user data.** Serialization is best-effort: unknown objects
   become `repr`, oversized payloads truncate, secrets redact — it never raises.
3. **Deterministic.** v1 writes synchronously, so a trace is on disk the instant
   a span ends; tests and the dashboard never race a background flush.

## Deliberate v1 divergences from the research brief

The [research synthesis](RESEARCH_SYNTHESIS.md) recommended a few things v1
intentionally defers, with rationale (see [ROADMAP.md](ROADMAP.md)):

- **Float epoch-seconds timestamps**, not integer nanoseconds. `float64` epoch
  seconds retains ~microsecond resolution — ample for agent-scale spans — and
  sibling ordering is handled by the per-run `seq` tiebreaker. ns is a clean
  future change behind the model.
- **Synchronous writes**, not a background writer thread. For a *local,
  single-user* debugging tool, WAL-mode SQLite writes are sub-millisecond and
  the determinism is worth more than the throughput. The background writer is
  the right call at cloud/multi-tenant scale, not here.

Both are isolated behind `Tracer`/`Storage`, so adopting them later touches no
public API.
