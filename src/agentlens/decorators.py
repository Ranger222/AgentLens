"""The ``@trace`` decorator — the headline, lowest-friction instrumentation.

Works on sync functions, coroutines, generators, and async generators. Captures
the call's arguments as the span input and the return value as the span output
(both toggleable), records exceptions, and re-raises untouched.
"""

from __future__ import annotations

import functools
import inspect
import logging
from typing import Any, Callable, TypeVar, cast

from .models import Span, SpanType
from .tracer import Tracer, get_tracer

logger = logging.getLogger("agentlens")

F = TypeVar("F", bound=Callable[..., Any])


def _bind_args(fn: Callable[..., Any], args: tuple, kwargs: dict) -> dict[str, Any]:
    """Best-effort named argument capture; falls back to positional/keyword dump."""
    try:
        sig = inspect.signature(fn)
        bound = sig.bind_partial(*args, **kwargs)
        bound.apply_defaults()
        captured = dict(bound.arguments)
        captured.pop("self", None)
        captured.pop("cls", None)
        return captured
    except Exception:  # noqa: BLE001
        return {"args": list(args), "kwargs": dict(kwargs)}


def trace(
    func: F | None = None,
    *,
    name: str | None = None,
    type: str = SpanType.AGENT_STEP,
    capture_input: bool = True,
    capture_output: bool = True,
) -> F | Callable[[F], F]:
    """Decorate a function so each call is recorded as a span.

    Usable bare (``@trace``) or parameterized (``@trace(type="tool_call")``).
    """

    def decorator(fn: F) -> F:
        span_name: str = str(
            name or getattr(fn, "__qualname__", None) or getattr(fn, "__name__", "anonymous")
        )

        def _input(args: tuple, kwargs: dict) -> Any:
            return _bind_args(fn, args, kwargs) if capture_input else None

        if inspect.isasyncgenfunction(fn):

            @functools.wraps(fn)
            async def async_gen_wrapper(*args: Any, **kwargs: Any) -> Any:
                tracer = get_tracer()
                if not tracer.enabled:
                    async for item in fn(*args, **kwargs):
                        yield item
                    return
                s = _safe_start(tracer, span_name, type, _input(args, kwargs))
                if s is None:
                    async for item in fn(*args, **kwargs):
                        yield item
                    return
                err: Exception | None = None
                try:
                    async for item in fn(*args, **kwargs):
                        yield item
                except Exception as e:
                    err = e
                    raise
                finally:
                    tracer.end_span(s, error=err)

            return cast(F, async_gen_wrapper)

        if inspect.iscoroutinefunction(fn):

            @functools.wraps(fn)
            async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
                tracer = get_tracer()
                if not tracer.enabled:
                    return await fn(*args, **kwargs)
                s = _safe_start(tracer, span_name, type, _input(args, kwargs))
                if s is None:
                    return await fn(*args, **kwargs)
                try:
                    result = await fn(*args, **kwargs)
                except Exception as e:
                    tracer.end_span(s, error=e)
                    raise
                tracer.end_span(s, output=result if capture_output else None)
                return result

            return cast(F, async_wrapper)

        if inspect.isgeneratorfunction(fn):

            @functools.wraps(fn)
            def gen_wrapper(*args: Any, **kwargs: Any) -> Any:
                tracer = get_tracer()
                if not tracer.enabled:
                    yield from fn(*args, **kwargs)
                    return
                s = _safe_start(tracer, span_name, type, _input(args, kwargs))
                if s is None:
                    yield from fn(*args, **kwargs)
                    return
                err = None
                try:
                    yield from fn(*args, **kwargs)
                except Exception as e:
                    err = e
                    raise
                finally:
                    tracer.end_span(s, error=err)

            return cast(F, gen_wrapper)

        @functools.wraps(fn)
        def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
            tracer = get_tracer()
            if not tracer.enabled:
                return fn(*args, **kwargs)
            s = _safe_start(tracer, span_name, type, _input(args, kwargs))
            if s is None:
                return fn(*args, **kwargs)
            try:
                result = fn(*args, **kwargs)
            except Exception as e:
                tracer.end_span(s, error=e)
                raise
            tracer.end_span(s, output=result if capture_output else None)
            return result

        return cast(F, sync_wrapper)

    if func is not None and callable(func):
        return decorator(func)
    return decorator


def _safe_start(tracer: Tracer, name: str, type: str, input: Any) -> Span | None:
    try:
        return tracer.start_span(name, type=type, input=input)
    except Exception:  # noqa: BLE001
        logger.debug("agentlens: failed to start span for %s", name, exc_info=True)
        return None
