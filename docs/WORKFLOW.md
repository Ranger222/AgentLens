# Development workflow

## The build loop

AgentLens v1 was built with a deliberate, repeatable loop:

```
research (agent-swarm)  →  design brief  →  implement  →  test  →  ./scripts/verify.sh
                                               ▲                          │
                                               └────── fix failures ◄─────┘   (loop until ALL GREEN)
```

1. **Research & brainstorm** — a parallel agent-swarm surveyed the competitive
   landscape, OTel/data-model conventions, instrumentation patterns, frontend
   viz, and DX/packaging. Output: [RESEARCH_SYNTHESIS.md](RESEARCH_SYNTHESIS.md).
2. **Design** — synthesized into decisions ([ARCHITECTURE.md](ARCHITECTURE.md),
   [DATA_MODEL.md](DATA_MODEL.md)); divergences recorded in [ROADMAP.md](ROADMAP.md).
3. **Implement** in dependency order: model → storage → tracer/context → SDK
   surface → instrumentation → backend → frontend → CLI.
4. **Test every layer** as it lands (see below).
5. **Verify** — `./scripts/verify.sh` is the single green-gate. The loop is:
   run it, fix the first failure, run it again, until it prints `ALL GREEN ✅`.

`scripts/verify.sh` *is* the harness — re-run it after any change. CI runs the
same gates on every push/PR (`.github/workflows/ci.yml`).

## One-time setup

```bash
make venv            # or: uv venv .venv
make install         # editable install + dev/server deps
make install-frontend
```

## Everyday commands

```bash
make test            # Python tests
make test-cov        # + coverage
make lint type       # ruff + mypy
make fmt             # ruff autofix + format
make frontend-test   # vitest
make demo            # generate sample traces (no API keys)
make serve           # launch the dashboard
make verify          # the full green-gate (./scripts/verify.sh)
```

## Verify harness gates

`./scripts/verify.sh` runs, in order, and fails on the first red:

| Gate | What it checks |
|---|---|
| ruff | lint of `src` + `tests` |
| mypy | static types |
| pytest | unit + integration (+ coverage) |
| frontend typecheck | `tsc --noEmit` |
| frontend tests | vitest |
| frontend build | `vite build` |
| packaging | wheel builds **and contains the bundled UI** |
| e2e | `demo` → `serve` → curl `/api/health`, `/api/runs`, `/` |

Skip slow steps with `SKIP_FRONTEND=1`, `SKIP_PACKAGING=1`, `SKIP_E2E=1`.

## Testing strategy

- **Highest value:** the parent-id correctness matrix in
  `tests/test_context_tracer.py` (sync, `asyncio.gather`, threads,
  `TracedThreadPoolExecutor`) — a misleading tree is worse than no tracing.
- `@trace` is tested across all four function shapes + the fail-silent path.
- Auto-instrumentation is tested by injecting **fake** `openai`/`anthropic`
  module trees into `sys.modules` — real monkeypatch path, zero network/keys.
- The API is tested with FastAPI's `TestClient`; the frontend waterfall math
  (`flatten`, `barGeometry`) is unit-tested with vitest.

## Git / branch strategy

Work happens on **`build/v1`**; `main` is reached via a reviewed **pull
request**, never a direct push. CI gates the PR. To publish your commits and
open/maintain the PR, see **[PUSHING.md](PUSHING.md)** (covers the credential
setup the dashboard build needs).

## Commit conventions

Conventional-commit prefixes (`feat:`, `fix:`, `test:`, `docs:`, `build:`,
`chore:`). Keep the working tree green — run `make verify` before committing
anything non-trivial.
