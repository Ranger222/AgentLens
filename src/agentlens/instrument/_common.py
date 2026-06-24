"""Shared machinery for auto-instrumenting LLM client SDKs.

The wrapper factory here is provider-agnostic: a provider module supplies a
``build_request`` (turn call kwargs into span input/model/name) and a
``parse_response`` (pull output text + token usage off the response). Keeping the
lifecycle here means OpenAI and Anthropic adapters are ~30 lines each, and the
tricky bits (sync vs async, error handling, streaming, never-raise) live in one
tested place.
"""

from __future__ import annotations

import functools
import inspect
import logging
from typing import Any, Callable, Dict, Optional

from ..models import SpanType, TokenUsage
from ..tracer import get_tracer

logger = logging.getLogger("agentlens")

# Provider parser signatures:
#   build_request(kwargs) -> {"name": str, "model": str|None, "input": Any, "metadata": dict}
#   parse_response(resp)  -> {"output": Any, "usage": TokenUsage|None, "model": str|None}
BuildRequest = Callable[[Dict[str, Any]], Dict[str, Any]]
ParseResponse = Callable[[Any], Dict[str, Any]]


def get_attr(obj: Any, key: str, default: Any = None) -> Any:
    """Read ``key`` whether ``obj`` is a pydantic-ish object or a plain dict."""
    if obj is None:
        return default
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def build_wrapper(
    original: Callable[..., Any],
    *,
    build_request: BuildRequest,
    parse_response: ParseResponse,
) -> Callable[..., Any]:
    """Wrap an SDK ``create``-style callable so each call records an ``llm_call`` span."""

    def _start(tracer: Any, kwargs: Dict[str, Any]):  # type: ignore[no-untyped-def]
        try:
            req = build_request(kwargs)
        except Exception:  # noqa: BLE001
            req = {"name": "llm_call", "model": kwargs.get("model"), "input": None, "metadata": {}}
        return tracer.start_span(
            req.get("name", "llm_call"),
            type=SpanType.LLM_CALL,
            input=req.get("input"),
            model=req.get("model"),
            metadata=req.get("metadata") or {},
        )

    def _finish(tracer: Any, span: Any, kwargs: Dict[str, Any], resp: Any) -> None:  # type: ignore[no-untyped-def]
        # Streaming responses are lazy iterators; capturing their full output
        # would require consuming them (and could break the caller). For v1 we
        # record the call + mark it streaming, leaving output capture to later.
        if kwargs.get("stream"):
            span.set_metadata(stream=True)
            tracer.end_span(span, status="ok")
            return
        output: Any = None
        usage: Optional[TokenUsage] = None
        try:
            parsed = parse_response(resp)
            output = parsed.get("output")
            usage = parsed.get("usage")
            if parsed.get("model"):
                span.model = parsed["model"]
        except Exception:  # noqa: BLE001
            logger.debug("agentlens: failed to parse LLM response", exc_info=True)
        tracer.end_span(span, output=output, usage=usage)

    if inspect.iscoroutinefunction(original):

        @functools.wraps(original)
        async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
            tracer = get_tracer()
            if not tracer.enabled:
                return await original(*args, **kwargs)
            try:
                span = _start(tracer, kwargs)
            except Exception:  # noqa: BLE001
                return await original(*args, **kwargs)
            try:
                resp = await original(*args, **kwargs)
            except Exception as e:
                tracer.end_span(span, error=e)
                raise
            _finish(tracer, span, kwargs, resp)
            return resp

        return async_wrapper

    @functools.wraps(original)
    def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
        tracer = get_tracer()
        if not tracer.enabled:
            return original(*args, **kwargs)
        try:
            span = _start(tracer, kwargs)
        except Exception:  # noqa: BLE001
            return original(*args, **kwargs)
        try:
            resp = original(*args, **kwargs)
        except Exception as e:
            tracer.end_span(span, error=e)
            raise
        _finish(tracer, span, kwargs, resp)
        return resp

    return sync_wrapper
