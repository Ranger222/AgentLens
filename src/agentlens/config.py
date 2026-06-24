"""Configuration & environment resolution for the SDK."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Optional

from .serialization import DEFAULT_MAX_VALUE_LEN

DEFAULT_DB_FILENAME = "agentlens.db"

ENV_DB = "AGENTLENS_DB"
ENV_DISABLED = "AGENTLENS_DISABLED"
ENV_CAPTURE_IO = "AGENTLENS_CAPTURE_IO"
ENV_MAX_VALUE_LEN = "AGENTLENS_MAX_VALUE_LEN"


def _env_bool(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def resolve_db_path(db_path: Optional[str] = None) -> str:
    """Resolve the SQLite path with one shared precedence (SDK and dashboard).

    ``explicit arg`` → ``$AGENTLENS_DB`` → ``./agentlens.db`` (if CWD writable)
    → ``~/.agentlens/agentlens.db``.

    The home-dir fallback prevents the #1 footgun: the SDK writing ``./agentlens.db``
    while ``serve`` reads somewhere else. Both call this resolver.
    """
    if db_path:
        return os.path.abspath(os.path.expanduser(db_path))
    env = os.environ.get(ENV_DB)
    if env:
        return os.path.abspath(os.path.expanduser(env))
    cwd = os.getcwd()
    if os.access(cwd, os.W_OK):
        return os.path.join(cwd, DEFAULT_DB_FILENAME)
    return os.path.abspath(os.path.expanduser(os.path.join("~", ".agentlens", DEFAULT_DB_FILENAME)))


@dataclass
class Config:
    """Resolved SDK configuration.

    ``enabled=False`` makes ``@trace``/``span()`` near no-ops (user code still
    runs); useful in production or tests. ``capture_io=False`` keeps the span
    tree/timings but drops potentially-sensitive inputs/outputs.
    """

    db_path: str = field(default_factory=resolve_db_path)
    enabled: bool = True
    capture_io: bool = True
    max_value_len: int = DEFAULT_MAX_VALUE_LEN

    @classmethod
    def from_env(cls, **overrides: object) -> Config:
        cfg = cls(
            db_path=resolve_db_path(overrides.get("db_path")),  # type: ignore[arg-type]
            enabled=_env_bool(ENV_DISABLED, False) is False,
            capture_io=_env_bool(ENV_CAPTURE_IO, True),
            max_value_len=int(os.environ.get(ENV_MAX_VALUE_LEN, DEFAULT_MAX_VALUE_LEN)),
        )
        for key, value in overrides.items():
            if value is not None and hasattr(cfg, key):
                setattr(cfg, key, value)
        return cfg
