#!/usr/bin/env bash
# LensTrace verify harness — the single source of truth for "is the build green?"
#
# Runs every quality gate: Python lint (ruff), types (mypy), tests (pytest+cov),
# the frontend (typecheck, vitest, build), a packaging check (wheel includes the
# UI), and an end-to-end smoke (demo -> serve -> curl the API).
#
# Usage:   ./scripts/verify.sh
# Env:     SKIP_FRONTEND=1   skip the npm steps
#          SKIP_PACKAGING=1  skip the wheel build
#          SKIP_E2E=1        skip the live-server smoke
#
# Exits non-zero if ANY step fails, printing a summary. Designed to be looped on.
set -uo pipefail

cd "$(dirname "$0")/.."
ROOT="$(pwd)"
PORT="${LENSTRACE_VERIFY_PORT:-8799}"

# ---- pretty output -----------------------------------------------------------
if [ -t 1 ]; then BOLD=$'\033[1m'; RED=$'\033[31m'; GRN=$'\033[32m'; YLW=$'\033[33m'; RST=$'\033[0m'
else BOLD=""; RED=""; GRN=""; YLW=""; RST=""; fi

RESULTS=()
FAILED=0

step() {
  local name="$1"; shift
  printf "\n${BOLD}▶ %s${RST}\n" "$name"
  if "$@"; then
    RESULTS+=("${GRN}✓${RST} $name"); printf "${GRN}✓ %s${RST}\n" "$name"
  else
    RESULTS+=("${RED}✗${RST} $name"); printf "${RED}✗ %s FAILED${RST}\n" "$name"; FAILED=1
  fi
}

# ---- resolve the python interpreter -----------------------------------------
if [ -x "$ROOT/.venv/bin/python" ]; then PY="$ROOT/.venv/bin/python"; else PY="python3"; fi
echo "Using Python: $($PY --version 2>&1) ($PY)"

# ---- Python gates ------------------------------------------------------------
step "ruff (lint)"        "$PY" -m ruff check src tests
step "mypy (types)"       "$PY" -m mypy
step "pytest (unit+integration)" "$PY" -m pytest -q --cov=lenstrace --cov-report=term-missing:skip-covered

# ---- Frontend gates ----------------------------------------------------------
if [ "${SKIP_FRONTEND:-0}" != "1" ]; then
  if command -v npm >/dev/null 2>&1; then
    pushd frontend >/dev/null
    [ -d node_modules ] || step "npm install" npm install --no-audit --no-fund
    step "frontend typecheck" npm run typecheck
    step "frontend tests (vitest)" npm run test
    step "frontend build (vite)" npm run build
    popd >/dev/null
  else
    echo "${YLW}! npm not found — skipping frontend${RST}"
  fi
fi

# ---- Packaging: wheel must contain the built UI ------------------------------
if [ "${SKIP_PACKAGING:-0}" != "1" ]; then
  if [ -f frontend/dist/index.html ]; then
    step "vendor UI into package" bash -c "rm -rf src/lenstrace/_webui && cp -r frontend/dist src/lenstrace/_webui"
    step "build wheel" "$PY" -m build --wheel --no-isolation
    step "wheel contains _webui" bash -c "$PY -m zipfile -l dist/lenstrace-*.whl | grep -q 'lenstrace/_webui/index.html'"
    # keep the package clean for dev (server falls back to frontend/dist)
    rm -rf src/lenstrace/_webui
  else
    echo "${YLW}! frontend/dist missing — skipping packaging (run the frontend build first)${RST}"
  fi
fi

# ---- E2E smoke: demo -> serve -> curl ----------------------------------------
if [ "${SKIP_E2E:-0}" != "1" ]; then
  E2E_DB="$(mktemp -d)/lenstrace.db"
  step "e2e: demo writes a run" "$PY" -m lenstrace.cli demo --db "$E2E_DB" -n 1 --seed 1
  "$PY" -m lenstrace.cli serve --db "$E2E_DB" --no-browser --host 127.0.0.1 --port "$PORT" >/tmp/lenstrace_verify_serve.log 2>&1 &
  SERVE_PID=$!
  trap '[ -n "${SERVE_PID:-}" ] && kill "$SERVE_PID" 2>/dev/null || true' EXIT
  ready=0
  for _ in $(seq 1 40); do
    if curl -sf "http://127.0.0.1:$PORT/api/health" >/dev/null 2>&1; then ready=1; break; fi
    sleep 0.25
  done
  step "e2e: server health" bash -c "[ $ready -eq 1 ]"
  step "e2e: /api/runs returns the run" bash -c "curl -sf 'http://127.0.0.1:$PORT/api/runs' | grep -q research_agent"
  step "e2e: UI is served at /" bash -c "curl -sf 'http://127.0.0.1:$PORT/' | grep -qi '<!doctype html'"
  kill "$SERVE_PID" 2>/dev/null || true
  SERVE_PID=""
fi

# ---- summary -----------------------------------------------------------------
printf "\n${BOLD}── verify summary ──${RST}\n"
for r in "${RESULTS[@]}"; do printf "  %b\n" "$r"; done
if [ "$FAILED" -eq 0 ]; then
  printf "\n${GRN}${BOLD}ALL GREEN ✅${RST}\n"; exit 0
else
  printf "\n${RED}${BOLD}VERIFY FAILED ❌${RST}\n"; exit 1
fi
