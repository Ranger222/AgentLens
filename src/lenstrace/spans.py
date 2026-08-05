"""The ``span()`` context manager and the manual ``start_span``/``end_span`` API.

These are the lowest-friction primitives: open a span around any block of work,
record output/usage on it, and it nests automatically under whatever span is
already active in the current context.
"""

from __future__ import annotations

import logging
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

from .models import Run, Span, SpanType, TokenUsage
from .tracer import get_tracer

logger = logging.getLogger("lenstrace")


@contextmanager
def run(name: str | None = None, *, metadata: dict[str, Any] | None = None) -> Iterator[Run | None]:
    """Explicitly group several top-level spans into one run.

    Optional — the first span you open auto-creates a run. Use this only when you
    want multiple sibling top-level spans under a single named run::

        with run("nightly-batch"):
            process(a)   # each its own top-level span, same run
            process(b)
    """
    tracer = get_tracer()
    if not tracer.enabled:
        yield None
        return
    try:
        r = tracer.start_run(name, metadata=metadata)
    except Exception:  # noqa: BLE001
        logger.debug("lenstrace: failed to start run", exc_info=True)
        yield None
        return
    err: BaseException | None = None
    try:
        yield r
    except Exception as e:
        err = e
        raise
    finally:
        tracer.end_run(r, error=err if isinstance(err, Exception) else None)


def _detached_span(name: str, type: str) -> Span:
    """A throwaway span (no run, never persisted) yielded when tracing is off or
    failed to start — so user code calling ``s.set_output(...)`` still works."""
    return Span(span_id="", run_id="", name=name, type=type)


@contextmanager
def span(
    name: str,
    *,
    type: str = SpanType.AGENT_STEP,
    input: Any = None,
    model: str | None = None,
    metadata: dict[str, Any] | None = None,
    run_name: str | None = None,
) -> Iterator[Span]:
    """Trace a block of work.

    Example::

        with span("search", type="tool_call", input=query) as s:
            results = do_search(query)
            s.set_output(results)
    """
    tracer = get_tracer()
    if not tracer.enabled:
        yield _detached_span(name, type)
        return

    try:
        s = tracer.start_span(
            name, type=type, input=input, model=model, metadata=metadata, run_name=run_name
        )
    except Exception:  # noqa: BLE001 - never let instrumentation break the caller
        logger.debug("lenstrace: failed to start span", exc_info=True)
        yield _detached_span(name, type)
        return

    err: BaseException | None = None
    try:
        yield s
    except Exception as e:
        err = e
        raise
    finally:
        tracer.end_span(s, error=err if isinstance(err, Exception) else None)


def start_span(
    name: str,
    *,
    type: str = SpanType.AGENT_STEP,
    input: Any = None,
    model: str | None = None,
    metadata: dict[str, Any] | None = None,
    run_name: str | None = None,
) -> Span:
    """Manually open a span. Pair with :func:`end_span` (same context)."""
    tracer = get_tracer()
    if not tracer.enabled:
        return _detached_span(name, type)
    return tracer.start_span(
        name, type=type, input=input, model=model, metadata=metadata, run_name=run_name
    )


def end_span(
    span: Span,
    *,
    output: Any = None,
    error: BaseException | None = None,
    usage: TokenUsage | None = None,
    status: str | None = None,
) -> None:
    """Manually close a span previously opened with :func:`start_span`."""
    tracer = get_tracer()
    if not tracer.enabled or not span.span_id:
        return
    tracer.end_span(span, output=output, error=error, usage=usage, status=status)
