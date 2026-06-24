"""The tracer: run/span lifecycle, context nesting, persistence.

Design rules:
- **Never break user code.** Every storage interaction is wrapped; a failing
  backend degrades to "no trace", not a crashed agent.
- **Nesting is automatic** via contextvars: the first span opened with no active
  run creates the run and "owns" it; closing that span finalizes the run.
- **Durations are monotonic**: ``end_time`` is ``start_time`` (wall clock) plus a
  ``perf_counter`` delta, so it's accurate and never precedes the start.
"""

from __future__ import annotations

import logging
import sys
import threading
import time
import traceback
from contextvars import Token
from dataclasses import dataclass
from typing import Any, Callable

from . import context as _ctx
from .config import Config
from .ids import new_run_id, new_span_id
from .models import ErrorInfo, Run, Span, SpanStatus, SpanType, TokenUsage
from .storage.base import Storage

logger = logging.getLogger("agentlens")


@dataclass
class _SpanState:
    """Internal per-span bookkeeping kept off the public model."""

    perf_start: float
    span_token: Token
    owns_run: bool
    run: Run
    run_token: Token | None
    parent_span: Span | None = None


class Tracer:
    def __init__(self, config: Config, storage: Storage | None = None) -> None:
        self.config = config
        self._storage = storage
        self._active: dict[str, _SpanState] = {}
        # Runs (by id) that have seen at least one errored span — for status rollup.
        self._run_errors: set = set()
        # Tokens for explicitly-started runs (agentlens.run(...)).
        self._run_tokens: dict[str, Token] = {}
        self._announced = False
        self._lock = threading.Lock()

    # --------------------------------------------------------------- plumbing
    @property
    def enabled(self) -> bool:
        return self.config.enabled

    @property
    def storage(self) -> Storage:
        """Lazily open the SQLite backend on first use (cheap import otherwise)."""
        if self._storage is None:
            from .storage.sqlite import SQLiteStorage

            self._storage = SQLiteStorage(
                self.config.db_path, max_value_len=self.config.max_value_len
            )
            self._announce_path()
        return self._storage

    def _announce_path(self) -> None:
        """Print where traces are going (once) — kills the 'serve shows no runs' footgun."""
        if self._announced:
            return
        self._announced = True
        try:
            sys.stderr.write(f"🔍 AgentLens: writing traces to {self.config.db_path}\n")
        except Exception:  # noqa: BLE001
            pass

    @staticmethod
    def _safe(fn: Callable[[], Any]) -> None:
        try:
            fn()
        except Exception:  # noqa: BLE001 - tracing must never raise into user code
            logger.debug("agentlens: storage operation failed", exc_info=True)

    # ---------------------------------------------------------------- spans
    def start_span(
        self,
        name: str,
        *,
        type: str = SpanType.AGENT_STEP,
        input: Any = None,
        model: str | None = None,
        metadata: dict[str, Any] | None = None,
        run_name: str | None = None,
    ) -> Span:
        """Open a span. Creates the run if none is active in this context."""
        now_wall = time.time()
        perf = time.perf_counter()

        run = _ctx.current_run()
        owns_run = False
        run_token: Token | None = None
        if run is None:
            run = Run(
                run_id=new_run_id(),
                name=run_name or name,
                start_time=now_wall,
                status=SpanStatus.RUNNING,
            )
            run_token = _ctx.push_run(run)
            owns_run = True
            self._safe(lambda: self.storage.save_run(run))

        parent = _ctx.current_span()
        span = Span(
            span_id=new_span_id(),
            run_id=run.run_id,
            name=name,
            type=type,
            parent_id=parent.span_id if parent else None,
            start_time=now_wall,
            status=SpanStatus.RUNNING,
            input=input if self.config.capture_io else None,
            model=model,
            metadata=dict(metadata) if metadata else {},
        )
        span_token = _ctx.push_span(span)
        with self._lock:
            self._active[span.span_id] = _SpanState(
                perf_start=perf,
                span_token=span_token,
                owns_run=owns_run,
                run=run,
                run_token=run_token,
                parent_span=parent,
            )
        self._safe(lambda: self.storage.save_span(span))
        return span

    def end_span(
        self,
        span: Span,
        *,
        output: Any = None,
        error: BaseException | None = None,
        usage: TokenUsage | None = None,
        status: str | None = None,
    ) -> None:
        """Close a span, persist it, and (if it owns the run) finalize the run."""
        with self._lock:
            state = self._active.pop(span.span_id, None)

        if state is not None:
            span.end_time = span.start_time + (time.perf_counter() - state.perf_start)
        else:  # span wasn't tracked (double-end / cross-context) — degrade gracefully
            span.end_time = time.time()

        if output is not None and self.config.capture_io:
            span.output = output
        if not self.config.capture_io:
            span.input = None
            span.output = None
        if usage is not None:
            span.usage = usage
        if error is not None:
            span.error = ErrorInfo.from_exception(
                error, "".join(traceback.format_exception(type(error), error, error.__traceback__))
            )
            span.status = SpanStatus.ERROR
        elif status is not None:
            span.status = status
        elif span.status == SpanStatus.RUNNING:
            span.status = SpanStatus.OK

        if span.is_error:
            self._run_errors.add(span.run_id)

        self._safe(lambda: self.storage.update_span(span))

        if state is not None:
            _ctx.pop_span(state.span_token, fallback=state.parent_span)
            if state.owns_run:
                run = state.run
                run.end_time = span.end_time
                run.status = (
                    SpanStatus.ERROR if span.run_id in self._run_errors else SpanStatus.OK
                )
                self._run_errors.discard(span.run_id)
                self._safe(lambda: self.storage.update_run(run))
                if state.run_token is not None:
                    _ctx.pop_run(state.run_token)

    # ------------------------------------------------------------------ runs
    def start_run(self, name: str | None = None, *, metadata: dict[str, Any] | None = None) -> Run:
        """Explicitly open a run so several top-level spans group together."""
        run = Run(
            run_id=new_run_id(),
            name=name,
            start_time=time.time(),
            status=SpanStatus.RUNNING,
            metadata=dict(metadata) if metadata else {},
        )
        token = _ctx.push_run(run)
        with self._lock:
            self._run_tokens[run.run_id] = token
        self._safe(lambda: self.storage.save_run(run))
        return run

    def end_run(self, run: Run, *, error: BaseException | None = None) -> None:
        run.end_time = time.time()
        errored = error is not None or run.run_id in self._run_errors
        run.status = SpanStatus.ERROR if errored else SpanStatus.OK
        self._run_errors.discard(run.run_id)
        self._safe(lambda: self.storage.update_run(run))
        with self._lock:
            token = self._run_tokens.pop(run.run_id, None)
        if token is not None:
            _ctx.pop_run(token)

    # ----------------------------------------------------------------- admin
    def flush(self) -> None:
        """No-op placeholder (writes are synchronous in v1)."""

    def close(self) -> None:
        if self._storage is not None:
            self._storage.close()


# --------------------------------------------------------------------- global
_global_tracer: Tracer | None = None
_global_lock = threading.Lock()


def configure(
    db_path: str | None = None,
    *,
    enabled: bool | None = None,
    capture_io: bool | None = None,
    max_value_len: int | None = None,
    storage: Storage | None = None,
) -> Tracer:
    """Configure (and return) the global tracer. Safe to call more than once."""
    global _global_tracer
    cfg = Config.from_env(
        db_path=db_path,
        enabled=enabled,
        capture_io=capture_io,
        max_value_len=max_value_len,
    )
    with _global_lock:
        if _global_tracer is not None:
            _global_tracer.close()
        _global_tracer = Tracer(cfg, storage=storage)
    return _global_tracer


def get_tracer() -> Tracer:
    """Return the global tracer, creating a default one (from env) on first use."""
    global _global_tracer
    if _global_tracer is None:
        with _global_lock:
            if _global_tracer is None:
                _global_tracer = Tracer(Config.from_env())
    return _global_tracer


def shutdown() -> None:
    """Close the global tracer and reset it (mostly for tests)."""
    global _global_tracer
    with _global_lock:
        if _global_tracer is not None:
            _global_tracer.close()
            _global_tracer = None
