"""FastAPI application factory for the AgentLens dashboard.

Serves a JSON API over the SQLite trace store and (when built) the React SPA as
static files. The app opens its own read-mostly SQLite connection on the same
file the SDK writes to — WAL mode makes that cross-process access safe.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from .._version import __version__
from ..config import resolve_db_path
from ..storage.sqlite import SQLiteStorage
from .schemas import run_detail


def find_webui_dir() -> Path | None:
    """Locate the built frontend: packaged ``_webui`` first, then dev ``frontend/dist``."""
    pkg_webui = Path(__file__).resolve().parent.parent / "_webui"
    if (pkg_webui / "index.html").exists():
        return pkg_webui
    # repo root is src/agentlens/server/app.py -> up 4 = repo root
    repo_dist = Path(__file__).resolve().parents[3] / "frontend" / "dist"
    if (repo_dist / "index.html").exists():
        return repo_dist
    return None


_PLACEHOLDER_HTML = """<!doctype html><html lang="en"><head><meta charset="utf-8">
<title>AgentLens</title><meta name="viewport" content="width=device-width, initial-scale=1">
<style>body{{background:#0b0e14;color:#e6e6e6;font-family:ui-sans-serif,system-ui,sans-serif;
display:flex;align-items:center;justify-content:center;min-height:100vh;margin:0}}
.card{{max-width:640px;padding:2rem;line-height:1.6}}code{{background:#1a1f2b;padding:.15rem .4rem;
border-radius:4px;color:#7dd3fc}}a{{color:#7dd3fc}}h1{{margin-top:0}}</style></head>
<body><div class="card"><h1>🔍 AgentLens API is running</h1>
<p>The dashboard UI hasn't been built yet. The JSON API is live:</p>
<ul><li><a href="/api/runs">/api/runs</a> — list runs</li>
<li><a href="/docs">/docs</a> — interactive API docs</li></ul>
<p>To build the UI for development:</p>
<p><code>cd frontend &amp;&amp; npm install &amp;&amp; npm run build</code></p>
<p>Then restart <code>agentlens serve</code>.</p></div></body></html>"""


def create_app(db_path: str | None = None) -> Any:
    """Build and return the FastAPI app bound to ``db_path``."""
    from fastapi import FastAPI, HTTPException, Query
    from fastapi.middleware.cors import CORSMiddleware
    from fastapi.responses import HTMLResponse
    from fastapi.staticfiles import StaticFiles

    resolved_db = resolve_db_path(db_path)
    app = FastAPI(
        title="AgentLens",
        version=__version__,
        description="Local-first tracing & observability for Python LLM-agent systems.",
    )

    # Permissive CORS so the Vite dev server (localhost:5173) can call the API.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    def storage() -> SQLiteStorage:
        # One connection per app instance; SQLiteStorage is internally locked.
        if not hasattr(app.state, "storage") or app.state.storage is None:
            os.makedirs(os.path.dirname(resolved_db) or ".", exist_ok=True)
            app.state.storage = SQLiteStorage(resolved_db)
        return app.state.storage

    @app.get("/api/health")
    def health() -> dict:
        return {
            "status": "ok",
            "version": __version__,
            "db_path": resolved_db,
            "db_exists": os.path.exists(resolved_db),
        }

    @app.get("/api/runs")
    def list_runs(
        limit: int = Query(50, ge=1, le=500),
        offset: int = Query(0, ge=0),
    ) -> dict:
        store = storage()
        runs = store.list_runs(limit=limit, offset=offset)
        return {
            "runs": [r.to_dict() for r in runs],
            "total": store.count_runs(),
            "limit": limit,
            "offset": offset,
        }

    @app.get("/api/runs/{run_id}")
    def get_run(run_id: str) -> dict:
        store = storage()
        run = store.get_run(run_id)
        if run is None:
            raise HTTPException(status_code=404, detail=f"run '{run_id}' not found")
        spans = store.get_spans(run_id)
        return run_detail(run, spans)

    @app.get("/api/runs/{run_id}/spans/{span_id}")
    def get_span(run_id: str, span_id: str) -> dict:
        store = storage()
        span = store.get_span(run_id, span_id)
        if span is None:
            raise HTTPException(status_code=404, detail=f"span '{span_id}' not found")
        return span.to_dict()

    @app.delete("/api/runs/{run_id}")
    def delete_run(run_id: str) -> dict:
        store = storage()
        deleted = store.delete_run(run_id)
        if not deleted:
            raise HTTPException(status_code=404, detail=f"run '{run_id}' not found")
        return {"deleted": True, "run_id": run_id}

    # ------------------------------------------------------------- static UI
    webui = find_webui_dir()
    if webui is not None:
        # html=True serves index.html at "/" and 404s missing files; API routes
        # registered above take precedence over this mount.
        app.mount("/", StaticFiles(directory=str(webui), html=True), name="webui")
    else:

        @app.get("/", response_class=HTMLResponse)
        def index() -> str:
            return _PLACEHOLDER_HTML

    return app
