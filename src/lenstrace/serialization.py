"""Safe, best-effort serialization of arbitrary Python values for storage.

Tracing must never crash user code, so serialization is defensive: anything
that cannot be represented as JSON is converted to a string via ``repr`` (or a
type-aware shim), and oversized payloads are truncated. The result of
:func:`to_jsonable` is always JSON-serializable.
"""

from __future__ import annotations

import dataclasses
import json
from typing import Any

DEFAULT_MAX_VALUE_LEN = 64 * 1024  # 64 KiB cap on a single serialized value
_MAX_DEPTH = 8
_MAX_ITEMS = 1000  # cap list/dict fan-out so one giant container can't explode
_TRUNCATION_SUFFIX = "…[truncated]"

REDACTED = "[redacted]"
# Keys whose values are scrubbed before storage. Matching is normalized
# (lowercased, with '-'/'_'/' ' removed) so "api_key", "API-Key", "apiKey" all hit.
_DEFAULT_REDACT_KEYS = frozenset(
    {
        "apikey",
        "authorization",
        "xapikey",
        "token",
        "accesstoken",
        "refreshtoken",
        "secret",
        "clientsecret",
        "password",
        "openaiapikey",
        "anthropicapikey",
    }
)


def _normalize_key(key: object) -> str:
    return str(key).lower().replace("-", "").replace("_", "").replace(" ", "")


def is_secret_key(key: object) -> bool:
    """True if ``key`` looks like a credential we should never persist."""
    return _normalize_key(key) in _DEFAULT_REDACT_KEYS


def to_jsonable(obj: Any, *, _depth: int = 0) -> Any:
    """Convert ``obj`` into a JSON-serializable structure, defensively.

    Handles the common cases that show up in agent code: primitives, dicts,
    lists/tuples/sets, dataclasses, pydantic models (v1 & v2), bytes, and
    objects exposing ``to_dict``/``dict``/``model_dump``. Unknown objects fall
    back to ``repr``. Never raises.
    """
    if obj is None or isinstance(obj, (bool, int, float, str)):
        return obj

    if _depth >= _MAX_DEPTH:
        return _safe_repr(obj)

    try:
        # pydantic v2
        if hasattr(obj, "model_dump") and callable(obj.model_dump):
            return to_jsonable(obj.model_dump(), _depth=_depth + 1)
        # pydantic v1 / objects exposing dict()
        if hasattr(obj, "dict") and callable(obj.dict) and not isinstance(obj, type):
            try:
                return to_jsonable(obj.dict(), _depth=_depth + 1)
            except TypeError:
                pass  # some .dict() need args; fall through
        if dataclasses.is_dataclass(obj) and not isinstance(obj, type):
            return to_jsonable(dataclasses.asdict(obj), _depth=_depth + 1)
        if isinstance(obj, dict):
            out: dict[str, Any] = {}
            for i, (k, v) in enumerate(obj.items()):
                if i >= _MAX_ITEMS:
                    out["…"] = f"[{len(obj) - _MAX_ITEMS} more items]"
                    break
                if is_secret_key(k):
                    out[str(k)] = REDACTED
                    continue
                out[str(k)] = to_jsonable(v, _depth=_depth + 1)
            return out
        if isinstance(obj, (list, tuple, set, frozenset)):
            seq = list(obj)
            items = [to_jsonable(v, _depth=_depth + 1) for v in seq[:_MAX_ITEMS]]
            if len(seq) > _MAX_ITEMS:
                items.append(f"…[{len(seq) - _MAX_ITEMS} more items]")
            return items
        if isinstance(obj, (bytes, bytearray)):
            return _safe_decode(obj)
        if hasattr(obj, "to_dict") and callable(obj.to_dict):
            return to_jsonable(obj.to_dict(), _depth=_depth + 1)
    except Exception:  # noqa: BLE001 - serialization is strictly best-effort
        return _safe_repr(obj)

    return _safe_repr(obj)


def dumps(obj: Any, *, max_len: int = DEFAULT_MAX_VALUE_LEN) -> str:
    """Serialize ``obj`` to a JSON string, truncating if it exceeds ``max_len``."""
    jsonable = to_jsonable(obj)
    try:
        text = json.dumps(jsonable, ensure_ascii=False, default=_safe_repr)
    except Exception:  # noqa: BLE001
        text = json.dumps(_safe_repr(obj))
    if max_len and len(text) > max_len:
        text = text[:max_len] + _TRUNCATION_SUFFIX
    return text


def loads(text: str | None) -> Any:
    """Parse a stored JSON string back into a Python value.

    Tolerates ``None`` and truncated/invalid JSON (returns the raw string so the
    UI can still show *something* rather than erroring).
    """
    if text is None:
        return None
    try:
        return json.loads(text)
    except (json.JSONDecodeError, TypeError):
        return text


def _safe_repr(obj: Any) -> str:
    try:
        r = repr(obj)
    except Exception:  # noqa: BLE001
        r = f"<unreprable {type(obj).__name__}>"
    if len(r) > DEFAULT_MAX_VALUE_LEN:
        r = r[:DEFAULT_MAX_VALUE_LEN] + _TRUNCATION_SUFFIX
    return r


def _safe_decode(b: bytes | bytearray) -> str:
    try:
        s = bytes(b).decode("utf-8")
        if len(s) > DEFAULT_MAX_VALUE_LEN:
            s = s[:DEFAULT_MAX_VALUE_LEN] + _TRUNCATION_SUFFIX
        return s
    except UnicodeDecodeError:
        return f"<{len(b)} bytes>"
