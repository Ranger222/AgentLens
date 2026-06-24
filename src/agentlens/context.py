"""Async/thread-safe ambient context for the current run and span.

Built on :mod:`contextvars`, the same mechanism OpenTelemetry uses. Each
asyncio task and each thread (when started via a copied context) sees its own
"current span", so parent/child nesting is inferred automatically without the
user threading anything through their call signatures.
"""

from __future__ import annotations

from contextvars import ContextVar, Token
from typing import Optional

from .models import Run, Span

_current_span: ContextVar[Optional[Span]] = ContextVar("agentlens_current_span", default=None)
_current_run: ContextVar[Optional[Run]] = ContextVar("agentlens_current_run", default=None)


def current_span() -> Optional[Span]:
    """Return the innermost active span in this context, if any."""
    return _current_span.get()


def current_run() -> Optional[Run]:
    """Return the active run in this context, if any."""
    return _current_run.get()


def push_span(span: Span) -> Token:
    """Set ``span`` as current; return a token to pass to :func:`pop_span`."""
    return _current_span.set(span)


def pop_span(token: Token, fallback: Optional[Span] = None) -> None:
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


def pop_run(token: Token, fallback: Optional[Run] = None) -> None:
    try:
        _current_run.reset(token)
    except (ValueError, LookupError):
        _current_run.set(fallback)
