"""SQLite-backed storage.

A single connection (``check_same_thread=False``) guarded by a lock serializes
access from the SDK side, while WAL mode lets a separate dashboard *process*
read the same file concurrently. That's the whole concurrency story: simple,
local, no server.
"""

from __future__ import annotations

import os
import sqlite3
import threading
import time

from ..models import ErrorInfo, Run, RunSummary, Span, TokenUsage
from ..serialization import DEFAULT_MAX_VALUE_LEN, dumps, loads
from .base import Storage

_SCHEMA = """
CREATE TABLE IF NOT EXISTS runs (
    run_id     TEXT PRIMARY KEY,
    name       TEXT,
    start_time REAL NOT NULL,
    end_time   REAL,
    status     TEXT NOT NULL,
    metadata   TEXT,
    created_at REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS spans (
    span_id      TEXT PRIMARY KEY,
    run_id       TEXT NOT NULL,
    parent_id    TEXT,
    name         TEXT NOT NULL,
    type         TEXT NOT NULL,
    start_time   REAL NOT NULL,
    end_time     REAL,
    status       TEXT NOT NULL,
    input        TEXT,
    output       TEXT,
    error        TEXT,
    usage        TEXT,
    total_tokens INTEGER,
    model        TEXT,
    metadata     TEXT,
    seq          INTEGER NOT NULL,
    FOREIGN KEY (run_id) REFERENCES runs(run_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_spans_run ON spans(run_id);
CREATE INDEX IF NOT EXISTS idx_spans_parent ON spans(parent_id);
CREATE INDEX IF NOT EXISTS idx_spans_run_order ON spans(run_id, start_time, seq);
CREATE INDEX IF NOT EXISTS idx_runs_start ON runs(start_time DESC);
"""

SCHEMA_VERSION = 1


class SQLiteStorage(Storage):
    def __init__(self, db_path: str, *, max_value_len: int = DEFAULT_MAX_VALUE_LEN) -> None:
        self.db_path = db_path
        self.max_value_len = max_value_len
        self._lock = threading.RLock()
        # Per-run insertion counter so save_span never does an O(n) COUNT(*).
        self._seq_counters: dict[str, int] = {}
        if db_path != ":memory:":
            parent = os.path.dirname(os.path.abspath(db_path))
            os.makedirs(parent, exist_ok=True)
        # ``:memory:`` is supported for tests; a file path is the norm.
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._init_db()

    def _init_db(self) -> None:
        with self._lock:
            cur = self._conn.cursor()
            # WAL doesn't apply to in-memory DBs; guard so tests don't warn.
            if self.db_path != ":memory:":
                cur.execute("PRAGMA journal_mode=WAL;")
            cur.execute("PRAGMA synchronous=NORMAL;")
            cur.execute("PRAGMA foreign_keys=ON;")
            cur.execute(f"PRAGMA user_version={SCHEMA_VERSION};")
            cur.executescript(_SCHEMA)
            self._conn.commit()

    # ------------------------------------------------------------------ runs
    def save_run(self, run: Run) -> None:
        with self._lock:
            self._conn.execute(
                """INSERT OR REPLACE INTO runs
                   (run_id, name, start_time, end_time, status, metadata, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (
                    run.run_id,
                    run.name,
                    run.start_time,
                    run.end_time,
                    run.status,
                    dumps(run.metadata, max_len=self.max_value_len) if run.metadata else None,
                    time.time(),
                ),
            )
            self._conn.commit()

    def update_run(self, run: Run) -> None:
        with self._lock:
            self._conn.execute(
                "UPDATE runs SET name=?, end_time=?, status=?, metadata=? WHERE run_id=?",
                (
                    run.name,
                    run.end_time,
                    run.status,
                    dumps(run.metadata, max_len=self.max_value_len) if run.metadata else None,
                    run.run_id,
                ),
            )
            self._conn.commit()

    def get_run(self, run_id: str) -> Run | None:
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM runs WHERE run_id=?", (run_id,)
            ).fetchone()
        return _row_to_run(row) if row else None

    def list_runs(self, *, limit: int = 50, offset: int = 0) -> list[RunSummary]:
        with self._lock:
            rows = self._conn.execute(
                """
                SELECT r.run_id, r.name, r.start_time, r.end_time, r.status, r.metadata,
                       COUNT(s.span_id) AS span_count,
                       COALESCE(SUM(CASE WHEN s.status='error' THEN 1 ELSE 0 END), 0) AS error_count,
                       SUM(s.total_tokens) AS total_tokens,
                       GROUP_CONCAT(s.model) AS models_concat
                FROM runs r
                LEFT JOIN spans s ON s.run_id = r.run_id
                GROUP BY r.run_id
                ORDER BY r.start_time DESC
                LIMIT ? OFFSET ?
                """,
                (limit, offset),
            ).fetchall()
        return [
            RunSummary(
                run_id=row["run_id"],
                name=row["name"],
                start_time=row["start_time"],
                end_time=row["end_time"],
                status=row["status"],
                span_count=row["span_count"] or 0,
                error_count=row["error_count"] or 0,
                total_tokens=row["total_tokens"],
                models=_count_models(row["models_concat"]),
                metadata=loads(row["metadata"]) or {},
            )
            for row in rows
        ]

    def count_runs(self) -> int:
        with self._lock:
            row = self._conn.execute("SELECT COUNT(*) AS n FROM runs").fetchone()
        return int(row["n"]) if row else 0

    def delete_run(self, run_id: str) -> bool:
        with self._lock:
            cur = self._conn.execute("DELETE FROM runs WHERE run_id=?", (run_id,))
            # Belt-and-suspenders: explicit child delete in case FK pragma is off.
            self._conn.execute("DELETE FROM spans WHERE run_id=?", (run_id,))
            self._conn.commit()
            self._seq_counters.pop(run_id, None)
            return cur.rowcount > 0

    # ----------------------------------------------------------------- spans
    def save_span(self, span: Span) -> None:
        with self._lock:
            span.seq = self._next_seq(span.run_id)
            self._conn.execute(
                """INSERT OR REPLACE INTO spans
                   (span_id, run_id, parent_id, name, type, start_time, end_time, status,
                    input, output, error, usage, total_tokens, model, metadata, seq)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                self._span_params(span),
            )
            self._conn.commit()

    def update_span(self, span: Span) -> None:
        with self._lock:
            self._conn.execute(
                """UPDATE spans SET
                     parent_id=?, name=?, type=?, start_time=?, end_time=?, status=?,
                     input=?, output=?, error=?, usage=?, total_tokens=?, model=?, metadata=?
                   WHERE span_id=?""",
                (
                    span.parent_id,
                    span.name,
                    span.type,
                    span.start_time,
                    span.end_time,
                    span.status,
                    self._enc(span.input),
                    self._enc(span.output),
                    dumps(span.error.to_dict(), max_len=self.max_value_len) if span.error else None,
                    dumps(span.usage.to_dict(), max_len=self.max_value_len) if span.usage else None,
                    span.usage.total_tokens if span.usage else None,
                    span.model,
                    dumps(span.metadata, max_len=self.max_value_len) if span.metadata else None,
                    span.span_id,
                ),
            )
            self._conn.commit()

    def get_spans(self, run_id: str) -> list[Span]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM spans WHERE run_id=? ORDER BY start_time ASC, seq ASC",
                (run_id,),
            ).fetchall()
        return [_row_to_span(row) for row in rows]

    def get_span(self, run_id: str, span_id: str) -> Span | None:
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM spans WHERE run_id=? AND span_id=?", (run_id, span_id)
            ).fetchone()
        return _row_to_span(row) if row else None

    def close(self) -> None:
        with self._lock:
            try:
                self._conn.close()
            except sqlite3.Error:  # pragma: no cover
                pass

    # --------------------------------------------------------------- helpers
    def _next_seq(self, run_id: str) -> int:
        """Next per-run insertion index. O(1) via an in-memory counter; falls
        back to ``MAX(seq)+1`` once per run for runs already on disk."""
        cached = self._seq_counters.get(run_id)
        if cached is None:
            row = self._conn.execute(
                "SELECT MAX(seq) AS m FROM spans WHERE run_id=?", (run_id,)
            ).fetchone()
            cached = (int(row["m"]) + 1) if row and row["m"] is not None else 0
        self._seq_counters[run_id] = cached + 1
        return cached

    def _enc(self, value: object) -> str | None:
        if value is None:
            return None
        return dumps(value, max_len=self.max_value_len)

    def _span_params(self, span: Span) -> tuple:
        return (
            span.span_id,
            span.run_id,
            span.parent_id,
            span.name,
            span.type,
            span.start_time,
            span.end_time,
            span.status,
            self._enc(span.input),
            self._enc(span.output),
            dumps(span.error.to_dict(), max_len=self.max_value_len) if span.error else None,
            dumps(span.usage.to_dict(), max_len=self.max_value_len) if span.usage else None,
            span.usage.total_tokens if span.usage else None,
            span.model,
            dumps(span.metadata, max_len=self.max_value_len) if span.metadata else None,
            span.seq,
        )


def _count_models(concat: str | None) -> dict[str, int]:
    """Turn a GROUP_CONCAT(model) string into ``{model: count}`` (NULLs skipped by SQL)."""
    if not concat:
        return {}
    counts: dict[str, int] = {}
    for model in concat.split(","):
        model = model.strip()
        if model:
            counts[model] = counts.get(model, 0) + 1
    return counts


def _row_to_run(row: sqlite3.Row) -> Run:
    return Run(
        run_id=row["run_id"],
        name=row["name"],
        start_time=row["start_time"],
        end_time=row["end_time"],
        status=row["status"],
        metadata=loads(row["metadata"]) or {},
    )


def _row_to_span(row: sqlite3.Row) -> Span:
    return Span(
        span_id=row["span_id"],
        run_id=row["run_id"],
        parent_id=row["parent_id"],
        name=row["name"],
        type=row["type"],
        start_time=row["start_time"],
        end_time=row["end_time"],
        status=row["status"],
        input=loads(row["input"]),
        output=loads(row["output"]),
        error=ErrorInfo.from_dict(loads(row["error"])),
        usage=TokenUsage.from_dict(loads(row["usage"])),
        model=row["model"],
        metadata=loads(row["metadata"]) or {},
        seq=row["seq"],
    )
