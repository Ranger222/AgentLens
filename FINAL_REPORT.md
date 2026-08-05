<!-- LensTrace final report — generated 2026-06-28 -->

# LensTrace — Final Audit & Deployment-Readiness Report

**Date:** 2026-06-28
**Prepared by:** Orchestrated agent-swarm audit + independent runtime verification
**Repo:** `github.com/Ranger222/LensTrace` · branch `build/v1` · commit `55ded72`

---

## How this report was produced (methodology)

An *orchestrator + agent-swarm* protocol:

- **4 parallel review agents** independently audited the codebase across four lenses — **security**, **unwanted/dead code**, **deployment readiness**, and **correctness** — reading the actual source with file/grep/shell tools.
- **Every raw finding was adversarially verified** by a dedicated skeptic agent that re-read the code and judged each against LensTrace's *local-first, single-user, loopback-by-default* threat model (so severities are realistic, not boilerplate). Result: **18 findings → 18 confirmed/adjusted, 0 rejected**.
- A **lead-reviewer agent synthesized** the verified findings into §1–§8 below.
- 23 agents / ~503k tokens total. One deployment sub-agent hit a transient API error mid-run; its core points (UI vendoring, PyPI name, `.gitignore` path) were independently re-confirmed and are reflected below.

## Independent runtime verification (by the reviewer — executed, not inferred)

**Unit tests — PASS**

| Suite | Result |
|---|---|
| Python (pytest) | **129 passed**, **87% line coverage** — verified on Python **3.9** and **3.10** with `openai`+`anthropic` extras installed |
| Lint / types | **ruff** clean, **mypy** clean |
| Frontend (Vitest) | **15 passed** |
| GitHub CI | **green** — Python 3.9/3.10/3.11/3.12 + frontend + wheel-package jobs |

**Clean-wheel deployment serve test — PASS** *(important nuance to the "deployment ready: NO" verdict in §5)*

A wheel was built with the dashboard vendored into `src/lenstrace/_webui/`, installed into a **fresh** virtualenv (simulating a real `pip install`), and `lenstrace serve` was launched from that install:

- `index.html` present inside the installed package ✅
- `GET /api/health` → ok; `GET /api/runs` returns data ✅
- `GET /` serves the **real built dashboard** from the wheel (`id="root"` + hashed `assets/index-*.js/.css`), not the placeholder ✅

**Reconciliation of the deployment verdict:** the application *runs and serves correctly in deployment when the wheel is built with the UI vendored* — which the CI `package` job already does. The "deployment ready: NO" verdict below is about **release-process gaps, not the app's runtime ability**: there is no automated/documented vendoring step for a *manual* `python -m build` (a naive build would ship the placeholder), the `.gitignore` protects the wrong path (`sdk/` vs `src/`), and the PyPI distribution name `lenstrace` is already taken. These are real and should be cleared before a public release, but the core **capture → store → serve** loop is verified working.

---

## 1. Executive Summary

LensTrace is a well-built, test-covered, single-user developer tool. The code quality is good, the never-raise tracing contract is largely honored, and the architecture (lazy FastAPI import, stdlib-only core, single locked SQLite connection) is sound for its stated local-first model.

The review found **0 critical** and **1 high** issue. The single high-severity finding is a **correctness bug in the headline `@trace` API**: a cancelled async coroutine leaks its span permanently in `RUNNING` state and mislabels cancelled work as `ok`. For an observability tool, a tracer that corrupts its own traces under a common async condition (timeouts, task cancellation) is the most important issue to fix and is the primary functional blocker.

The medium-severity findings are all **security hardening gaps that are real but conditional** in the local-first model: wildcard CORS lets a malicious website the developer visits read captured prompts cross-origin; `--host 0.0.0.0` publishes the unauthenticated prompt API to the LAN with no warning; and redaction is key-only and overstated as "Secrets-safe" in the README. None are default-insecure, but each weakens a protection that a local dev tool should keep.

The remaining findings are low/info: developer-local git hygiene, doc drift, a stale `.gitignore` path, and a set of latent correctness landmines (none currently reachable through the shipped code path).

### Overall risk verdict: **MEDIUM**

Driven by the one high-severity correctness bug plus three medium security-hardening gaps. There are no critical or remotely-exploitable-by-default issues; the high finding is a self-corruption/data-integrity bug, not a breach.

### Deployment ready? **NO — conditional**

This is **not a security blocker** but there are **release blockers** that must be addressed before publishing a package/release:

1. **The high-severity cancelled-coroutine span leak** (`decorators.py`) should be fixed before tagging a release — it corrupts the core product's output under ordinary async usage.
2. **Wheel vendoring is broken/unverified:** the built dashboard is expected at `src/lenstrace/_webui/` (per `pyproject.toml:63` `artifacts = ["src/lenstrace/_webui/**"]` and `server/app.py:22`), but that directory **does not exist on disk** — the only build output is at `frontend/dist/`. A wheel built today ships **without the dashboard**, so `lenstrace serve` would render the placeholder HTML, not the UI. The frontend build must be vendored into `src/lenstrace/_webui/` as part of the release process.
3. **`.gitignore` ignores the wrong path** (`sdk/lenstrace/_webui/` vs the real `src/lenstrace/_webui/`), so once that build dir is populated for vendoring it is not actually protected from accidental `git add -A` staging of dev-time output.
4. **PyPI name `lenstrace`:** `pyproject.toml` declares `name = "lenstrace"`. This is a common name and must be confirmed available (or claimed) on PyPI before `twine upload`; verify before release.

Once the high-severity fix lands, the dashboard is correctly vendored into `src/lenstrace/_webui/`, and the PyPI name is confirmed, LensTrace is fit to ship as a `0.1.0` alpha.

### Finding counts (final, post-verification severities)

| Severity | Count |
|----------|-------|
| Critical | 0 |
| High | 1 |
| Medium | 3 |
| Low | 6 |
| Info | 8 |

---

## 2. Test Results

| Suite | Result | Notes |
|-------|--------|-------|
| Python (pytest) | **129 passed**, **87% coverage** | Healthy coverage for an alpha SDK. |
| Frontend (Vitest/React) | **15 passed** | Dashboard unit tests green. |

Test health is good. Note that the confirmed high-severity cancelled-coroutine bug and several latent correctness landmines (`build_span_tree` cycles, `INSERT OR REPLACE` cascade, `_run_errors` lock) are **not currently covered** by tests — regression tests for these are recommended (see P0/P1).

---

## 3. Security Findings

All severities below are judged in the **local-first, 127.0.0.1, single-user** threat model. "No auth on a loopback dashboard" is correctly treated as by-design and not flagged; the findings here are cases where a *browser same-origin protection* or a *stated guarantee* is weakened.

### Medium

#### S-1. Wildcard CORS (`allow_origins=["*"]`) on the unauthenticated prompt API
- **Location:** `src/lenstrace/server/app.py:62-67`
- **What:** `create_app()` unconditionally installs `CORSMiddleware` with `allow_origins=["*"]`, `allow_methods=["*"]`, `allow_headers=["*"]`, justified in-comment only to let the Vite dev server (`localhost:5173`) call the API.
- **Why it matters (local-first):** The API (`/api/runs`, `/api/runs/{id}`, `/api/runs/{id}/spans/{id}`) returns full span data via `Span.to_dict()` (`schemas.py:44-49`), including captured LLM **input/output** — raw prompts and completions that routinely contain PII/proprietary data. Wildcard CORS specifically defeats the browser same-origin protection that would otherwise shield a loopback dev server. Because `allow_credentials` is unset, simple cross-origin GETs from **any website the developer visits** while `lenstrace serve` is running can fetch `http://127.0.0.1:8765/api/runs` and read every captured prompt. This is a genuine (if conditional — needs the server running and a malicious page that knows port 8765) drive-by data-exfiltration vector.
- **Fix:** Replace `allow_origins=["*"]` with an explicit dev-origin allowlist (`http://localhost:5173`, `http://127.0.0.1:5173`, `http://localhost:8765`, `http://127.0.0.1:8765`). The production SPA is served same-origin by FastAPI's `StaticFiles` mount and needs **no CORS at all**; optionally only register CORS behind a dev/`--reload` flag. Do **not** add `allow_credentials=True` (not needed — no cookies/auth).

#### S-2. `--host 0.0.0.0` publishes the unauthenticated prompt API to the LAN with no warning
- **Location:** `src/lenstrace/cli.py:42` (free-form `--host`), passed verbatim to `uvicorn.run(host=args.host)` at `cli.py:83`/`89`; server has no auth (`server/app.py`).
- **What:** `--host` is a free-form string (default `127.0.0.1`) passed straight to uvicorn with no validation and **no warning** when a non-loopback host is chosen (`cli.py:67-70` prints only the URL).
- **Why it matters (local-first):** This is exactly the higher-risk case the threat model carves out. `lenstrace serve --host 0.0.0.0` (a common "let me view it from another machine" reflex) immediately publishes the entire unauthenticated trace API — returning captured prompts, completions, and tool args (`models.py:120-121` confirms `input`/`output` fields) — to every host on the LAN, with wildcard CORS on top. No token, no confirmation, no caution in README/help. Severity stays medium (not higher) because the default is safe and this requires deliberate user action — an ergonomic foot-gun, not a default-insecure flaw, and the data is the dev's own traces on their own LAN.
- **Fix:** In `_cmd_serve`, treat `{127.0.0.1, ::1, localhost}` as loopback; for anything else print a prominent stderr warning ("binding to a non-loopback address exposes your unauthenticated trace API — captured prompts, completions, tool args — to every host on your network"), and require an explicit opt-in (`--allow-remote` or interactive TTY confirmation) before binding non-loopback, exiting non-zero otherwise. Optionally generate a one-time access token enforced on API routes when bound remotely. Document the exposure.

#### S-3. Redaction is exact-key-only, misses common secret keys, never scrubs values — contradicts README "Secrets-safe" claim
- **Location:** `src/lenstrace/serialization.py:23-46, 75-99`; README claim at `README.md:100`.
- **What:** `is_secret_key` checks `_normalize_key(key) in _DEFAULT_REDACT_KEYS` — exact-membership against an 11-key frozenset. It correctly recurses into nested dicts and covers core names (`api_key`, `authorization`, `token`/`accesstoken`/`refreshtoken`, `password`, `secret`, `openai/anthropic api key`). But it **omits** many widely-used secret keys: `cookie`, `set-cookie`, `bearer`, `aws_secret_access_key`, `aws_access_key_id`, `private_key`, `credentials`, `connection_string`/`dsn`, `session_token`, `passphrase`, `pat`, and `x-auth-token` (normalizes to `xauthtoken`, absent). Redaction is **key-based only**: secrets appearing as a string *value* (a prompt like `"use key sk-abc123"`), a bare positional list element (`["--api-key","sk-..."]`, recursed at `:86-91` with no key context), or the Anthropic `system` prompt copied to metadata (`instrument/anthropic.py:24-25`) are persisted verbatim. README.md:100 advertises "**Secrets-safe** — api_key / authorization / token values are redacted … before they're ever written to disk," overstating a best-effort, key-only mechanism.
- **Why it matters (local-first):** Leaked secrets land in a SQLite file owned by the same user who already has them — no remote exposure by default — so this is not high/critical. It stays above low because (a) plaintext secrets on disk leak via committed/shared trace DBs, screenshots, or bug-report attachments, and (b) the affirmative "Secrets-safe" claim can induce users to put real secrets in prompts under false confidence.
- **Fix:** (1) Expand `_DEFAULT_REDACT_KEYS` (add `cookie`, `setcookie`, `bearer`, `awssecretaccesskey`, `awsaccesskeyid`, `privatekey`, `credentials`, `connectionstring`, `dsn`, `sessiontoken`, `passphrase`, `xauthtoken`, `pat`). (2) Match by substring on high-signal stems (normalized key *containing* `secret`/`token`/`password`/`apikey`/`credential`) to catch variants like `db_password_2`. (3) Add a best-effort value scrubber for known token shapes (`sk-…`/`sk-proj-…`, `AKIA[0-9A-Z]{16}`, `Bearer <jwt>`, long base64/hex), applied to string values and string list elements — closing the positional-arg and prompt-embedded gaps including the Anthropic system prompt. (4) Soften README.md:100 to state redaction is best-effort/key-based and recommend `LENSTRACE_CAPTURE_IO=0` for sensitive data.

### Low

#### S-4. Local git config credential helper echoes `$GITHUB_PAT`
- **Location:** `.git/config` `[credential] helper`
- **What:** The repo's **local** git config defines `helper = "!f() { echo username=x-access-token; echo \"password=$GITHUB_PAT\"; }; f"`, unconditionally echoing `$GITHUB_PAT` into git's credential flow.
- **Why it matters (local-first):** `.git/config` is inherently **untracked** (it lives in `.git/`, never indexed), so it ships nothing to clones and exposes nothing downstream. The configured remote is SSH (`git@github.com:Ranger222/LensTrace.git`), and SSH transport does not invoke credential helpers, so the helper is currently dormant. Residual risk: the helper is unscoped (no host binding / `useHttpPath`), so any **HTTPS** remote git contacts (a typo'd or malicious HTTPS remote) would receive the token. Developer-local hygiene only; token is described as read-only/fine-grained.
- **Fix:** Prefer SSH/`gh auth` and delete the helper (`git config --unset-all credential.helper`), since the remote is already SSH. If HTTPS pushes are needed, scope the helper per-URL under `[credential "https://github.com"]` with `useHttpPath = true`. Keep `GITHUB_PAT` minimally scoped. No change to shipped artifacts needed.

### Info

#### S-5. `eval()` on a hardcoded literal in demo/example code (not attacker-controlled)
- **Location:** `examples/fake_agent.py:48`
- **What:** `calculator()` does `return eval(expression)  # noqa: S307 - intentional, for the demo error case`, called only as `calculator("1 / 0")` (line 60) to produce a deliberate `ZeroDivisionError`. `expression` is never derived from network/file/user/LLM input in any shipped path; this is the only `eval()` in the repo. The shipped runtime demo (`src/lenstrace/demo.py:42-44`) uses a plain `_ = 1 / 0` with no eval.
- **Why it matters (local-first):** No injection vector exists. The only concern is example-hygiene: a reader who rewires `calculator()` to real LLM/tool output would create an arbitrary-code-execution sink.
- **Fix:** Add an inline comment that `eval()` must never receive untrusted/LLM-generated input, or replace with `ast.literal_eval` / a tiny arithmetic evaluator so the example doesn't model an unsafe pattern.

#### S-6. `db_path` taken from env/CLI and used unsanitized (no trust boundary crossed)
- **Location:** `src/lenstrace/config.py:34-42`, `src/lenstrace/storage/sqlite.py:67-71`, `src/lenstrace/server/app.py:72`
- **What:** `resolve_db_path()` expands `~`/abspaths from `--db`/`$LENSTRACE_DB` with no allowlist/containment; `SQLiteStorage.__init__` and the server's request-time `storage()` do `os.makedirs(dirname)` then `sqlite3.connect`, auto-creating arbitrary parent dirs.
- **Why it matters (local-first):** All three `db_path` sources are supplied by the same local user who runs the process — no untrusted input crosses a trust boundary, and no HTTP route accepts a `db_path` (the server captures it once from trusted config at `create_app()`). This is the user choosing where their own file lives, not path traversal.
- **Fix:** No change for the current model. If multi-source/remote config is ever added, validate `db_path` against an expected base dir (`os.path.commonpath([base, resolved]) == base`) before `makedirs`/`connect`.

#### S-7. Dashboard opens a read/write SQLite connection (not read-only)
- **Location:** `src/lenstrace/server/app.py:69-74`, `src/lenstrace/storage/sqlite.py:71`
- **What:** The docstring calls the connection "read-mostly," but `sqlite3.connect(db_path, check_same_thread=False)` has no `mode=ro`/`immutable`/`PRAGMA query_only`, and `DELETE /api/runs/{run_id}` (`app.py:116-122` → `delete_run`, `sqlite.py:165-169`) genuinely writes. So an unauthenticated caller can delete trace data, not just read it.
- **Why it matters (local-first):** Delete-from-UI is an **intended feature**; a blanket read-only connection would break it. In the default loopback config this is fine; impact rises only in the optional `0.0.0.0` exposure scenario, and even then the worst case is deletion of the dev's own local traces. The "read-mostly" docstring is honest, not misleading.
- **Fix:** No change for default loopback. If remote exposure is supported, gate mutating endpoints behind an explicit opt-in (`--allow-delete`, default off) or register the delete route only on loopback — rather than forcing the shared connection read-only (which would break the SDK writer).

---

## 4. Code Hygiene / Unwanted Code

### Low

#### H-1. Stale `.gitignore` path for the vendored web UI build dir (`sdk/` vs `src/`) — *adjusted medium → low*
- **Location:** `.gitignore:71`
- **What:** `.gitignore` ignores `sdk/lenstrace/_webui/`, but no `sdk/` directory exists; the real packaged build location is `src/lenstrace/_webui/` (confirmed by `server/app.py:22` `parent.parent / "_webui"` and `pyproject.toml:63` `artifacts = ["src/lenstrace/_webui/**"]`). The ignore rule targets a dead path, so a future build emitted into `src/lenstrace/_webui/` is **not** actually ignored.
- **Adjustment rationale:** The finding's evidence claimed the bundle is "present and untracked on disk" — this is **false**; `src/lenstrace/_webui/` does not currently exist (the only build output is `frontend/dist/`, correctly ignored at line 70). The risk is therefore **latent**, not active: it only materializes once someone wires a build into `src/lenstrace/_webui/` (which the release vendoring step requires) and then runs `git add -A`. Worst case is a compiled JS bundle accidentally committed — repo bloat, trivially reverted. Hence low, not medium.
- **Fix:** Change `.gitignore:71` to `src/lenstrace/_webui/`. (This intersects with the deployment-readiness vendoring item — see §5.)

#### H-2. Old placeholder name "LensTrace"/`lenstrace` lingers in docs
- **Location:** `docs/REQUIREMENTS.md:11,19`; `docs/RESEARCH_SYNTHESIS.md:510`
- **What:** The pre-rename placeholder name "LensTrace" (with `lenstrace serve` and an explicit "(placeholder name—suggest better if you have one)" note) still appears in two design docs; `RESEARCH_SYNTHESIS.md:510` itself flags the drift ("scrub the placeholder name before publish"). Case-insensitive grep confirms the old name is confined to these 3 doc lines — no source, CLI, or packaging uses it.
- **Why it matters:** Cosmetic doc drift that contradicts the shipped `lenstrace` name; zero functional/security impact.
- **Fix:** Replace the 3 occurrences with `LensTrace`/`lenstrace`, or add a one-line banner marking `REQUIREMENTS.md` as a superseded historical design doc.

### Info (intentional / confirmed non-issues)

#### H-3. `eval()` in example is intentional and demo-only — no action needed
- **Location:** `examples/fake_agent.py:48` — see S-5. Confirmed intentional (`# noqa: S307`, hardcoded `"1 / 0"`, docstring says "blows up on a divide-by-zero on purpose"); shipped demo avoids eval. Optional belt-and-suspenders only.

#### H-4. `print()`/emoji in CLI and tracer are legitimate user-facing output — not debug cruft
- **Location:** `src/lenstrace/cli.py:67-146`; `src/lenstrace/tracer.py:79`; `src/lenstrace/server/app.py:38`
- **What:** All `print()` calls are inside CLI subcommand handlers (serve/demo/info/version) — intended human-readable output. `tracer.py:79`'s `sys.stderr.write` is a deliberate **one-time** "writing traces to <path>" notice (guarded by `self._announced`, wrapped in try/except so it never raises into user code). Emojis appear only in CLI output, the placeholder HTML, and that notice — none in hot library paths (which use `logger.debug`, `tracer.py:88`). A grep confirms no other stdout/stderr writes in the library.
- **Fix:** None required. If strict stdout cleanliness for piping is ever wanted, route CLI output through a console/logging abstraction.

---

## 5. Deployment Readiness — Go / No-Go

### Verdict: **NO-GO until the blockers below are cleared.** (Conditional — none are security-critical; they are correctness + packaging.)

| # | Blocker | Severity | Evidence | Required action |
|---|---------|----------|----------|-----------------|
| B1 | **Cancelled-coroutine span leak** corrupts core `@trace` output | High (correctness) | `decorators.py:94-100` has no try/finally; cancelled coroutine leaves span `RUNNING`/`end_time=None`, leaks `_active`, mislabels CM spans `ok` | Fix `async_wrapper` (try/finally + BaseException handling) before tagging a release — see C-1 / P0 |
| B2 | **Dashboard not vendored into the wheel** | Release-blocking (packaging) | `pyproject.toml:63` expects `src/lenstrace/_webui/**`; `server/app.py:22` loads from there; directory **does not exist** — only `frontend/dist/` is built | Build the frontend and vendor it into `src/lenstrace/_webui/` as part of the release; otherwise `lenstrace serve` ships the placeholder HTML, not the UI |
| B3 | **`.gitignore` ignores wrong build path** | Low (hygiene, intersects B2) | `.gitignore:71` = `sdk/lenstrace/_webui/`; real path `src/lenstrace/_webui/` | Fix to `src/lenstrace/_webui/` so dev-time build output is actually ignored and not accidentally staged once B2 populates it |
| B4 | **PyPI name `lenstrace` not confirmed available** | Release-blocking (packaging) | `pyproject.toml:6` `name = "lenstrace"` | Confirm the name is free/claimable on PyPI before `twine upload`; reserve or rename if taken |

### Non-blocking but recommended before publish
- Tighten CORS (S-1) and add the non-loopback warning/opt-in (S-2) — both are small, lossless changes that materially harden the default browsing-while-serving and `--host 0.0.0.0` scenarios.
- Soften the README "Secrets-safe" claim and expand redaction (S-3).
- Scrub the "LensTrace" placeholder from docs (H-2).

The package metadata is otherwise in good shape: correct entry point (`lenstrace = lenstrace.cli:main`), MIT license declared, alpha classifier, lazy FastAPI deps, py3.9+ matrix. Once B1–B4 are cleared, LensTrace is fit to ship as `0.1.0` alpha.

---

## 6. Correctness / Bug Findings

### High

#### C-1. Cancelled traced coroutine leaks a span stuck in `RUNNING`; cancelled work mislabeled `ok`
- **Location:** `src/lenstrace/decorators.py:94-100` (`async_wrapper`); also `async_gen_wrapper:73-80`; `spans.py:93-97` and `:45-49`
- **What:** Since Python 3.8, `asyncio.CancelledError` subclasses **`BaseException`, not `Exception`**. `async_wrapper` has **no try/finally** — it does `except Exception as e: tracer.end_span(s, error=e); raise` and calls the success-path `end_span` on a separate line. When the awaited coroutine is cancelled, `CancelledError` bypasses both: `end_span` is **never called**. The span stays `status='running'`, `end_time=None` forever; its entry leaks in `tracer._active`; the contextvar token is never popped; and if it owns the run, the run is never finalized. **Reproduced:** a cancelled `@trace` coroutine persisted as `('slow', 'running', None)` with `_active` size 1. The `span()`/`run()` context managers *do* use try/finally, but pass `error=err if isinstance(err, Exception) else None` — so for `CancelledError`, `error=None` and the span is stamped `status='ok'`. **Reproduced:** `('slow-cm', 'ok', ...)` after cancellation. The same `except Exception` gap applies to `KeyboardInterrupt`/`SystemExit`/`GeneratorExit`.
- **Why it matters:** This is core-instrumentation data corruption in the headline `@trace` API. Cancellation is common in real async agent code (`asyncio.wait_for` timeouts, `TaskGroup` cancellation, client disconnects). The decorator leak is **unbounded** (growing `_active` + perpetually-`RUNNING` rows/runs polluting the dashboard), and an observability tool whose traces get stuck or mislabeled defeats its own purpose. Not security and not crash-level (user code still works, exceptions re-raise), so not critical — but high is well-calibrated.
- **Fix:** Restructure `async_wrapper` to try/finally like the generator wrappers so `end_span` always runs, catching `BaseException` and only passing `output` on the success path; record `CancelledError` as `status='cancelled'` (or error) instead of letting `isinstance(err, Exception)` collapse it to OK. Broaden the error/status decision to `BaseException` in `spans.py span()`/`run()` and the async-gen/gen wrappers. The **required** fix is the try/finally in `async_wrapper` to stop the RUNNING/`_active`/contextvar/run leak; correct status labelling is the secondary improvement.

### Low

#### C-2. `build_span_tree` drops ALL spans when `parent_id` forms a cycle — *adjusted medium → low*
- **Location:** `src/lenstrace/server/schemas.py:14-34`
- **What:** The docstring promises "nothing is ever dropped from the view," but a span is treated as a root only when its `parent_id` is absent from the node set. A 2-cycle (`s1.parent=s2`, `s2.parent=s1`) or self-cycle (`s.parent=s.span_id`) means every parent is present, so no node becomes a root and the entire run renders as an empty tree. **Reproduced:** 2-cycle → 0 roots; self-cycle → 0 roots (and an infinitely self-nested `children` structure that would `RecursionError` on JSON serialization). The flat `spans` list is still returned, so the tree silently disagrees with the flat view.
- **Adjustment rationale:** The technical claim is real and reproduced, but the **SDK cannot produce such data**: `tracer.py:120-125` assigns `parent_id` from the active span on a contextvar stack with a freshly generated `new_span_id()` per span, so every parent is a pre-existing ancestor — a write-path cycle is structurally impossible. A cycle requires a corrupted, hand-edited, or externally-written SQLite file. For a local-first single-user tool with no external writers, this is a defensive-robustness gap a normal user will never hit — hence low, not medium. The fix is cheap and the broken contract is documented, so it's worth addressing.
- **Fix:** After building child links, promote any node not reachable from a genuine root to a root (treat `parent is node` as a root for self-cycles; DFS from roots and append unvisited nodes for N-cycles). Add a unit test asserting `len(flatten(build_span_tree(spans))) == len(spans)` for self- and 2-cycles. Guard consumers walking `children` against infinite recursion.

#### C-3. `save_run` uses `INSERT OR REPLACE` with `ON DELETE CASCADE` — re-saving a run silently deletes all its spans
- **Location:** `src/lenstrace/storage/sqlite.py:88-104` (`save_run`) vs schema FK at `:48`
- **What:** `spans.run_id` has `FOREIGN KEY … ON DELETE CASCADE` with `PRAGMA foreign_keys=ON` (`:82`). `save_run` uses `INSERT OR REPLACE INTO runs`; SQLite's REPLACE **deletes** the conflicting parent row (firing the cascade) before inserting. **Reproduced** against the real class: `save_run('R')`; `save_span('x','R')` → 1 span; `save_run('R')` again → `get_spans('R')` returns 0, silently.
- **Why it matters:** Currently **latent** — the tracer calls `save_run` only once at run creation (`tracer.py:117`, `:211`) before any spans exist; all later mutations go through `update_run` (a plain UPDATE that doesn't cascade). The landmine fires only if future code re-saves a run or a user calls the public `storage.save_run(existing_run)` directly. Low for a single-user local tool — latent correctness, no active bug or security impact.
- **Fix:** Replace REPLACE with a non-destructive UPSERT (`INSERT … ON CONFLICT(run_id) DO UPDATE SET name=excluded.name, …`, leaving `created_at` unchanged) so the cascade never fires. Add a regression test (save_run; save_span; save_run; assert span survives).

#### C-4. `tracer._run_errors` read/mutated outside the lock guarding the rest of tracer state
- **Location:** `src/lenstrace/tracer.py:180-193, :216-218`
- **What:** `self._lock` protects `_active` and `_run_tokens`, but `_run_errors` (the per-run error-rollup set) is mutated/read entirely outside the lock: `end_span` does the unlocked `add` (181) and read+`discard` (190-193); `end_run` does an unlocked read+discard (216-218). Single set ops are GIL-atomic, but the read-at-191 / discard-at-193 pair is not atomic across calls, so with threaded fan-out (`TracedThreadPoolExecutor`) an error flag set by a sibling thread between the owner's membership test and discard can be lost — occasionally rolling a run up as `ok` when a child errored.
- **Why it matters:** Only manifests in unusual unsynchronized fan-out (the idiomatic `with pool:` joins workers via `shutdown(wait=True)` before the owner's read, so the common path is race-free). Impact is a cosmetic run-status label in a single-user tool — no data loss, no crash, tracing still never raises. Inconsistent with the locking discipline used elsewhere.
- **Fix:** Bring `_run_errors` under `self._lock` and make the read-then-discard a single critical section so no sibling `add` can slip between test and discard. Apply the same atomic read+discard in `end_run`.

### Info

#### C-5. `instrument._finish()` runs outside any try/except (defense-in-depth gap) — *adjusted low → info*
- **Location:** `src/lenstrace/instrument/_common.py:60-78`, called unguarded at `:96` and `:115`
- **What:** Both wrappers guard `_start()` and the original call in try/except, but the success-path `_finish(tracer, span, kwargs, resp)` is invoked **without** a guard.
- **Adjustment rationale:** The structural asymmetry is real, but every operation `_finish()` performs is already exception-safe: streaming `span.set_metadata(stream=True)` is `dict.update` on a guaranteed dict (cannot raise); `parse_response` is internally try/excepted; `tracer.end_span` wraps storage I/O in `Tracer._safe`, and the contextvar `pop_span`/`pop_run` paths the finding names are explicitly hardened in `context.py:42-45,53-56`. So there is **no live trigger** today — it's a latent asymmetry, not an actual bug, requiring a hypothetical future regression in `end_span` to manifest. Hence info, not low.
- **Fix:** Wrap both `_finish()` calls in `try/except Exception: logger.debug(..., exc_info=True)` to enforce the never-raise contract structurally. A 4-line change, no behavior change on any reachable path.

#### C-6. Generator / async-generator `@trace` wrappers never capture output and ignore `capture_output`
- **Location:** `src/lenstrace/decorators.py:58-82` (`async_gen_wrapper`), `:104-125` (`gen_wrapper`)
- **What:** The sync/async wrappers call `end_span(output=result if capture_output else None)`, but the generator wrappers only `yield from`/`async for … yield` and call `end_span(s, error=err)` with **no output** — `capture_output` is silently ignored, and nothing (not even item count) is recorded. The module docstring implies output capture is generically toggleable, overstating behavior for generators.
- **Why it matters:** Benign correctness/consistency gap — no security or data-loss impact, only reduced telemetry for users who use generators *and* expect output capture. Capturing generator output is legitimately non-trivial (lazy/infinite/side-effecting streams), so omitting it in v1 is defensible; the only real defect is that it's undocumented and inconsistent.
- **Fix:** Either document the limitation in `trace()`'s docstring, or (when `capture_output` and `config.capture_io` allow) accumulate yielded items into a bounded buffer or record a count, passing it as `output=` — never materializing unbounded generators (a count is the safest universal choice).

#### C-7. Per-run `seq` counter can duplicate across separate `SQLiteStorage` instances writing the same run
- **Location:** `src/lenstrace/storage/sqlite.py:236-246` (`_next_seq`), `:66` (`_seq_counters`)
- **What:** `_next_seq` seeds a per-run counter from `MAX(seq)+1` only on first use for that run on a given instance, then advances a process-local dict. If two `SQLiteStorage` instances write spans to the **same** `run_id` and the second seeds before the first commits, both can emit the same `seq`. `seq` is only an ordering tiebreaker (`idx_spans_run_order`, `ORDER BY start_time, seq`); `span_id` is the PRIMARY KEY, so rows never collide or lose data — only ordering of same-`start_time` siblings becomes ambiguous.
- **Why it matters:** The architecture deliberately avoids this — the SDK tracer is the sole writer (`tracer.py:142`), the FastAPI server's own `SQLiteStorage` (`app.py:73`) only reads. The author could not reproduce it in the sequential case. A genuine but inert edge case for a single-writer local tool.
- **Fix:** No change for current design. If cross-process writing is ever introduced, derive `seq` atomically in SQL (`COALESCE((SELECT MAX(seq)+1 …), 0)` within the locked transaction). Cheaper alternative: document the single-writer invariant next to `_seq_counters`.

---

## 7. Prioritized, Actionable Recommendations

### P0 — Must fix before release (blockers)
1. **Fix the cancelled-coroutine span leak (C-1).** Add try/finally to `async_wrapper` so `end_span` always runs on `CancelledError`/`BaseException`; label cancelled spans `cancelled`/error instead of leaving them `RUNNING` (decorator) or `ok` (CMs). Add async-cancellation regression tests. *This is the single most important fix — it corrupts the core product's output.*
2. **Vendor the dashboard into `src/lenstrace/_webui/` (B2)** as part of the release build, so the wheel actually ships the UI referenced by `pyproject.toml:63` / `app.py:22`.
3. **Confirm/claim the PyPI name `lenstrace` (B4)** before publishing.
4. **Fix `.gitignore:71`** `sdk/lenstrace/_webui/` → `src/lenstrace/_webui/` (H-1 / B3), so the vendored build dir is correctly ignored during dev once populated.

### P1 — Should fix before/with release (security hardening + cheap correctness)
5. **Restrict CORS (S-1)** to an explicit dev-origin allowlist (or gate behind `--reload`); production SPA needs none.
6. **Warn + opt-in for non-loopback `--host` (S-2)**; print a prominent warning and require `--allow-remote`/confirmation before binding `0.0.0.0`.
7. **Expand redaction + soften the README claim (S-3):** add missing secret keys, substring matching, a value-shape scrubber, and reword "Secrets-safe" to best-effort/key-based; recommend `LENSTRACE_CAPTURE_IO=0` for sensitive data.
8. **Harden `instrument._finish()` (C-5)** with a try/except guard to enforce the never-raise contract.
9. **Fix `save_run` UPSERT (C-3)** to remove the silent span-deletion landmine; add a regression test.

### P2 — Nice to have / defense-in-depth / hygiene
10. **Make `build_span_tree` cycle-safe (C-2)** with a reachability pass; assert `flatten == len(spans)`.
11. **Lock `_run_errors` (C-4)** for consistent rollup under threaded fan-out.
12. **Document or implement generator output capture (C-6).**
13. **Document the single-writer `seq` invariant or derive `seq` in SQL (C-7).**
14. **Scope or remove the git credential helper (S-4)** — prefer SSH/`gh auth`.
15. **Annotate or replace the example `eval()` (S-5).**
16. **Scrub "LensTrace"/`lenstrace` from docs (H-2).**

---

## 8. Appendix — Dismissed Findings

No findings were rejected during verification. Every finding surfaced in the review was either **confirmed** at its original severity or **adjusted** with documented rationale:

| Finding | Original | Final | Adjustment reason |
|---------|----------|-------|-------------------|
| `.gitignore` stale `_webui` path (H-1) | medium | **low** | Risk is latent — `src/lenstrace/_webui/` does not exist on disk; finding's "present and untracked" evidence was inaccurate. Worst case is accidental commit of a JS bundle, trivially reverted. |
| `build_span_tree` cycle drop (C-2) | medium | **low** | Technically reproduced, but the SDK cannot produce cyclic `parent_id` data; requires a corrupted/external SQLite file, which the single-user local model excludes. |
| `instrument._finish()` unguarded (C-5) | low | **info** | Real structural asymmetry, but every operation in `_finish()` is already exception-safe (including the contextvar paths the finding named), so there is no live trigger — a defense-in-depth note, not a bug. |

All other findings were **confirmed as-is**, including the several intentional/non-issue records (`eval()` demo-only, `print()`/emoji user-facing output, unsanitized `db_path` with no trust boundary, read/write dashboard connection enabling the intended delete feature) which were verified and correctly rated **info**.

---

*Report generated for `FINAL_REPORT.md`. Severity judgments reflect LensTrace's local-first, single-user, 127.0.0.1-by-default threat model: browser same-origin bypasses and stated-guarantee gaps are weighted up; "no auth on loopback" is by design and not flagged.*
