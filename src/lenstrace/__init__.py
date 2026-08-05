"""LensTrace — Chrome DevTools for your AI agents.

Local-first tracing & observability for Python LLM-agent systems. Instrument
with a decorator or context manager, store traces in SQLite, and inspect runs in
a local web dashboard (``lenstrace serve``).

Quick start::

    from lenstrace import trace, span

    @trace
    def my_agent(question: str) -> str:
        with span("search", type="tool_call", input=question) as s:
            results = search(question)
            s.set_output(results)
        return answer
"""

from __future__ import annotations

from ._version import __version__
from .concurrency import TracedThreadPoolExecutor
from .context import current_run, current_span
from .decorators import trace
from .instrument import (
    instrument_anthropic,
    instrument_openai,
    uninstrument_anthropic,
    uninstrument_openai,
)
from .models import ErrorInfo, Run, RunSummary, Span, SpanStatus, SpanType, TokenUsage
from .spans import end_span, run, span, start_span
from .tracer import Tracer, configure, get_tracer, shutdown

# Backwards/ergonomic alias: init() reads naturally next to configure().
init = configure

__all__ = [
    "__version__",
    # instrumentation API
    "trace",
    "span",
    "run",
    "start_span",
    "end_span",
    # configuration / lifecycle
    "configure",
    "init",
    "get_tracer",
    "shutdown",
    "Tracer",
    "TracedThreadPoolExecutor",
    # auto-instrumentation
    "instrument_openai",
    "uninstrument_openai",
    "instrument_anthropic",
    "uninstrument_anthropic",
    # context introspection
    "current_span",
    "current_run",
    # data model
    "Span",
    "Run",
    "RunSummary",
    "SpanType",
    "SpanStatus",
    "TokenUsage",
    "ErrorInfo",
]
