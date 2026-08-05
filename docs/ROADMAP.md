# Roadmap

## v1 (this release) — shipped

A genuinely usable, local-first agent tracer, end-to-end:

- ✅ Python SDK: `@trace` (sync/async/generator/async-gen), `span()` & `run()`
  context managers, manual `start_span`/`end_span`.
- ✅ Automatic parent/child nesting via `contextvars` (+ `TracedThreadPoolExecutor`).
- ✅ Auto-instrumentation for the raw OpenAI & Anthropic SDKs (idempotent).
- ✅ SQLite storage (WAL), a "run" groups nested spans.
- ✅ FastAPI backend + React/Vite dashboard: runs list, collapsible
  waterfall/tree, span detail, dark mode. One command: `lenstrace serve`.
- ✅ `lenstrace demo` — real nested-with-error trace, zero API keys.
- ✅ pip-installable, CLI entry point, 129 Python tests + 15 frontend tests, CI.

## Deferred (intentional v1 scope cuts, with rationale)

These were recommended by the [research synthesis](RESEARCH_SYNTHESIS.md) but
deliberately deferred to keep v1 tight, deterministic, and well-tested. Each is
isolated behind an existing seam, so adopting it later is non-breaking.

| Item | Why deferred | When it matters |
|---|---|---|
| **Nanosecond timestamps** | `float64` epoch seconds already give ~µs resolution; `seq` handles sibling ordering. | Sub-µs spans; exact OTLP export. |
| **Background writer thread** | Local single-user writes are sub-ms under WAL; sync writes are deterministic (no test/flush races). | High-throughput / cloud / multi-tenant. |
| **Full streaming capture** | v1 records the streamed call + marks `stream=True` without draining the user's iterator (safe). Capturing accumulated output/cumulative tokens has sharp edges (OpenAI `include_usage`, Anthropic cumulative `output_tokens`). | Token/cost accounting on streamed responses. |
| **`attributes` bag (gen_ai.*)** | `metadata` covers v1 needs; a separate canonical-key column buys OTel interop only. | OTLP export, cross-tool compatibility. |
| **OTLP exporter (`export --otlp`)** | The *seams* (hex ids, status map, type→kind map) are baked in; the exporter itself is out of v1 scope. | Sending traces to Jaeger/Phoenix/collectors. |
| **`capture_content` gate** | `capture_io` already lets users drop all I/O; redaction strips secrets. | Finer control over prompt-body capture. |

## Next up (post-v1 ideas)

- Framework integrations: LangChain callback handler, CrewAI, LlamaIndex.
- Live tail / auto-refresh of in-flight runs in the dashboard.
- Search & filter across runs (by status, model, token count, name).
- Cost estimation from token usage + a pricing table.
- Virtualized waterfall for runs with hundreds+ of spans.
- `lenstrace export --otlp` and an OpenInference-compatible exporter.
- Span diffing between two runs.

## Naming / publishing note

The brand is **LensTrace** and the CLI command is `lenstrace`. The project was
renamed from its original name (whose PyPI package was already taken by an
unrelated project) to **LensTrace** — the `lenstrace` distribution/import name
is verified available on PyPI, npm, and GitHub, so nothing blocks publishing.
