"""Async/thread-safe ambient context for the current run and span.

Built on :mod:`contextvars`, the same mechanism OpenTelemetry uses. Each
asyncio task and each thread (when started via a copied context) sees its own
"current span", so parent/child nesting is inferred automatically without the
user threading anything through their call signatures.
"""

from __future__ import annotations

from contextvars import ContextVar, Token

from .models import Run, Span

_current_span: ContextVar[Span | None] = ContextVar("lenstrace_current_span", default=None)
_current_run: ContextVar[Run | None] = ContextVar("lenstrace_current_run", default=None)


def current_span() -> Span | None:
    """Return the innermost active span in this context, if any."""
    return _current_span.get()


def current_run() -> Run | None:
    """Return the active run in this context, if any."""
    return _current_run.get()


def push_span(span: Span) -> Token:
    """Set ``span`` as current; return a token to pass to :func:`pop_span`."""
    return _current_span.set(span)


def pop_span(token: Token, fallback: Span | None = None) -> None:
    """Restore the previous current span.

    ``ContextVar.reset`` raises ``ValueError`` when set and reset happen in
    different contexts (e.g. across an ``asyncio.gather`` or thread boundary). We
    never let that escape into user code: on failure we explicitly restore the
    known parent instead.
    """
    try:
        _current_span.reset(token)
    except (ValueError, LookupError):
        _current_span.set(fallback)


def push_run(run: Run) -> Token:
    return _current_run.set(run)


def pop_run(token: Token, fallback: Run | None = None) -> None:
    try:
        _current_run.reset(token)
    except (ValueError, LookupError):
        _current_run.set(fallback)
