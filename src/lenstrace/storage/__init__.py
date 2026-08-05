"""Storage backends for runs and spans."""

from __future__ import annotations

from .base import Storage
from .sqlite import SQLiteStorage

__all__ = ["Storage", "SQLiteStorage"]
