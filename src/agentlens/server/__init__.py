"""The local dashboard backend (FastAPI). Imported only when serving."""

from __future__ import annotations

from .app import create_app

__all__ = ["create_app"]
