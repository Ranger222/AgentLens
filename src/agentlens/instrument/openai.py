"""Auto-instrumentation for the OpenAI Python SDK (v1.x).

``instrument_openai()`` monkeypatches ``chat.completions.create`` (sync + async)
so every call becomes an ``llm_call`` span with the request messages as input,
the completion text as output, and token usage filled in from ``response.usage``.
Idempotent; ``uninstrument_openai()`` restores the originals.
"""

from __future__ import annotations

from typing import Any, Dict

from ..models import TokenUsage
from ._common import build_wrapper, get_attr

_PATCHED: Dict[str, Any] = {}
_MARK = "_agentlens_wrapped"


def _build_request(kwargs: Dict[str, Any]) -> Dict[str, Any]:
    model = kwargs.get("model")
    messages = kwargs.get("messages")
    return {
        "name": f"openai.chat {model}" if model else "openai.chat.completions",
        "model": model,
        "input": messages if messages is not None else _scrub(kwargs),
        "metadata": {"provider": "openai"},
    }


def _scrub(kwargs: Dict[str, Any]) -> Dict[str, Any]:
    return {k: v for k, v in kwargs.items() if k not in {"api_key", "extra_headers"}}


def _parse_response(resp: Any) -> Dict[str, Any]:
    output: Any = None
    choices = get_attr(resp, "choices") or []
    if choices:
        message = get_attr(choices[0], "message")
        content = get_attr(message, "content")
        tool_calls = get_attr(message, "tool_calls")
        output = content if content is not None else tool_calls
    usage_obj = get_attr(resp, "usage")
    usage = None
    if usage_obj is not None:
        usage = TokenUsage(
            input_tokens=get_attr(usage_obj, "prompt_tokens"),
            output_tokens=get_attr(usage_obj, "completion_tokens"),
            total_tokens=get_attr(usage_obj, "total_tokens"),
        )
    return {"output": output, "usage": usage, "model": get_attr(resp, "model")}


def _wrap(original: Any) -> Any:
    wrapped = build_wrapper(original, build_request=_build_request, parse_response=_parse_response)
    setattr(wrapped, _MARK, True)
    return wrapped


def instrument_openai() -> None:
    """Patch the installed OpenAI SDK. Raises ImportError if openai isn't installed."""
    try:
        from openai.resources.chat import completions as _completions
    except Exception as exc:  # noqa: BLE001
        raise ImportError(
            "instrument_openai() requires the 'openai' package. Install with: pip install openai"
        ) from exc

    for cls_name in ("Completions", "AsyncCompletions"):
        cls = getattr(_completions, cls_name, None)
        if cls is None:
            continue
        original = cls.create
        if getattr(original, _MARK, False):
            continue  # already patched
        _PATCHED[cls_name] = original
        cls.create = _wrap(original)


def uninstrument_openai() -> None:
    """Restore the original OpenAI methods (no-op if not patched)."""
    try:
        from openai.resources.chat import completions as _completions
    except Exception:  # noqa: BLE001
        _PATCHED.clear()
        return
    for cls_name, original in list(_PATCHED.items()):
        cls = getattr(_completions, cls_name, None)
        if cls is not None:
            cls.create = original
    _PATCHED.clear()
