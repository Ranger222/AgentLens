"""Auto-instrumentation for the Anthropic Python SDK.

``instrument_anthropic()`` monkeypatches ``messages.create`` (sync + async) so
every call becomes an ``llm_call`` span: request messages as input, the response
content blocks as output, and ``input_tokens``/``output_tokens`` from
``response.usage``. Idempotent; ``uninstrument_anthropic()`` restores originals.
"""

from __future__ import annotations

from typing import Any

from ..models import TokenUsage
from ._common import build_wrapper, get_attr

_PATCHED: dict[str, Any] = {}
_MARK = "_lenstrace_wrapped"


def _build_request(kwargs: dict[str, Any]) -> dict[str, Any]:
    model = kwargs.get("model")
    messages = kwargs.get("messages")
    metadata: dict[str, Any] = {"provider": "anthropic"}
    if kwargs.get("system"):
        metadata["system"] = kwargs["system"]
    if kwargs.get("max_tokens") is not None:
        metadata["max_tokens"] = kwargs["max_tokens"]
    return {
        "name": f"anthropic.messages {model}" if model else "anthropic.messages",
        "model": model,
        "input": messages,
        "metadata": metadata,
    }


def _parse_response(resp: Any) -> dict[str, Any]:
    output: Any = get_attr(resp, "content")
    # Flatten content blocks to text when possible (nicer to read in the UI).
    if isinstance(output, list):
        texts: list[str] = []
        for block in output:
            text = get_attr(block, "text")
            if text:
                texts.append(text)
        if texts:
            output = "".join(texts) if len(texts) > 1 else texts[0]
    usage_obj = get_attr(resp, "usage")
    usage = None
    if usage_obj is not None:
        input_tokens = get_attr(usage_obj, "input_tokens")
        output_tokens = get_attr(usage_obj, "output_tokens")
        usage = TokenUsage(input_tokens=input_tokens, output_tokens=output_tokens)
    return {"output": output, "usage": usage, "model": get_attr(resp, "model")}


def _wrap(original: Any) -> Any:
    wrapped = build_wrapper(original, build_request=_build_request, parse_response=_parse_response)
    setattr(wrapped, _MARK, True)
    return wrapped


def instrument_anthropic() -> None:
    """Patch the installed Anthropic SDK. Raises ImportError if not installed."""
    try:
        from anthropic.resources import messages as _messages
    except Exception as exc:  # noqa: BLE001
        raise ImportError(
            "instrument_anthropic() requires the 'anthropic' package. "
            "Install with: pip install anthropic"
        ) from exc

    for cls_name in ("Messages", "AsyncMessages"):
        cls = getattr(_messages, cls_name, None)
        if cls is None:
            continue
        original = cls.create
        if getattr(original, _MARK, False):
            continue
        _PATCHED[cls_name] = original
        cls.create = _wrap(original)


def uninstrument_anthropic() -> None:
    """Restore the original Anthropic methods (no-op if not patched)."""
    try:
        from anthropic.resources import messages as _messages
    except Exception:  # noqa: BLE001
        _PATCHED.clear()
        return
    for cls_name, original in list(_PATCHED.items()):
        cls = getattr(_messages, cls_name, None)
        if cls is not None:
            cls.create = original
    _PATCHED.clear()
