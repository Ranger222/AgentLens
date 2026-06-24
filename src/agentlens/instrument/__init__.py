"""Auto-instrumentation adapters for raw LLM SDKs.

These import the underlying SDK lazily (inside the ``instrument_*`` functions),
so ``import agentlens`` never requires openai/anthropic to be installed.
"""

from __future__ import annotations

from .anthropic import instrument_anthropic, uninstrument_anthropic
from .openai import instrument_openai, uninstrument_openai

__all__ = [
    "instrument_openai",
    "uninstrument_openai",
    "instrument_anthropic",
    "uninstrument_anthropic",
]
