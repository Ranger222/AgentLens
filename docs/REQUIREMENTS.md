# Original Requirements (verbatim)

> This file preserves the original product brief that kicked off AgentLens, for
> traceability. The living design lives in [ARCHITECTURE.md](ARCHITECTURE.md),
> [DATA_MODEL.md](DATA_MODEL.md) and [WORKFLOW.md](WORKFLOW.md).

---

**Project: build an open-source observability/tracing tool for multi-agent and LLM-agent systems in Python.**

I'm building an MIT-licensed open-source developer tool called AgentTrace (placeholder name—suggest better if you have one). The goal is to let developers instrument their Python LLM agents and see what's happening inside a run: every LLM call, tool call, token count, latency, and error, visualized as a timeline. Think "Chrome DevTools for agent runs," running fully locally with zero external dependencies.

Target user: developers building agents with frameworks like LangChain, CrewAI, or raw OpenAI/Anthropic SDK calls, who currently debug with print statements and have no visibility into multi-step or multi-agent execution.

**Core requirements for v1 (keep scope tight):**

- A Python SDK that instruments agent code with minimal friction—a decorator (`@trace`) and/or a context manager, plus a way to wrap LLM client calls. It must be framework-agnostic: capture spans manually, and provide one example auto-instrumentation for the raw OpenAI/Anthropic SDK. Capturing a span records: name, type (llm_call / tool_call / agent_step), start/end time, latency, input, output, token usage if available, and error if thrown. Spans must nest to form a tree (parent/child) so multi-agent and multi-step runs show hierarchy.
- Local storage of traces—SQLite, no external services. A "run" groups many spans.
- A local web dashboard (FastAPI backend serving a React frontend) that lists runs and shows a single run as a collapsible timeline/tree: each span with its duration as a bar, expandable to see inputs/outputs/tokens/errors. Clean, readable, dark-mode-friendly. Launchable with one command (e.g. `agenttrace serve`).
- Packaging: pip-installable, a CLI entry point, and a one-command quickstart so someone can pip install, add the decorator, run their agent, and open the dashboard.

**Tech stack:** Python + FastAPI backend, SQLite storage, React (Vite) frontend. Use my existing comfort zone—Python, TypeScript, React, FastAPI, Docker.

**Deliverables for this first session:**

- Scaffold the full repo structure (SDK package, backend, frontend, examples, tests).
- Implement the core span/trace data model and the SDK (`@trace` decorator + context manager + manual span API).
- Wire SQLite persistence.
- Stub the FastAPI endpoints (list runs, get run with span tree).
- A working example script under `examples/` that instruments a small fake multi-step "agent" (two or three nested tool/LLM calls, one of which errors) so there's real data to view immediately—don't require real API keys to demo.
- A strong `README.md`: one-line pitch, the problem it solves, an animated-GIF placeholder, quickstart in under 5 commands, and a minimal code example showing the decorator.

**Principles:** prioritize a frictionless developer experience (the instrumentation API must feel trivial to add), keep v1 minimal but genuinely usable end-to-end, write clean idiomatic code with type hints, and make the example runnable with zero external API keys. Before writing code, propose the repo structure and the span data model, and briefly explain key design choices. Then build it.
