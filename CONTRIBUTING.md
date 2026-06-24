# Contributing to AgentLens

Thanks for your interest! AgentLens is MIT-licensed and local-first by design.

## Setup

```bash
git clone https://github.com/Ranger222/AgentLens
cd AgentLens
make venv && make install && make install-frontend
```

## Before you open a PR

Run the full green-gate — it's the same one CI runs:

```bash
make verify        # ruff + mypy + pytest + frontend + packaging + e2e
```

Or individual gates: `make lint type test frontend-test`.

## Guidelines

- **Keep the SDK core stdlib-only.** `import agentlens` must not require
  third-party packages. Put server deps behind lazy imports, SDK integrations
  behind their own optional extras.
- **Tracing must never break user code.** Wrap new side effects so a failure
  degrades to a missing span, never a raised exception (`tracer._safe`).
- **Type hints + tests** for new code. Match the surrounding style; `make fmt`
  applies ruff formatting.
- **Conventional commits** (`feat:`, `fix:`, `docs:`, `test:`, `build:`, `chore:`).
- New behavior needs a test. The parent/child nesting tests in
  `tests/test_context_tracer.py` are the bar for "is the tree correct".

## Project layout

```
src/agentlens/      SDK core, storage, instrumentation, server, CLI
frontend/           React + Vite + TS dashboard
examples/           runnable, zero-API-key examples
tests/              pytest suite
docs/               architecture, data model, workflow, roadmap
scripts/verify.sh   the green-gate
```

See [docs/WORKFLOW.md](docs/WORKFLOW.md) for the full development loop and
[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for how the pieces fit.

## Reporting bugs

Open an issue with a minimal repro. Because everything is local, attaching the
relevant `agentlens.db` (or the steps to reproduce one via `agentlens demo`)
makes triage fast.
