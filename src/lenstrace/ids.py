"""Identifier generation.

IDs are random hex strings, sized to loosely mirror OpenTelemetry: a run
(``trace``) id is 16 bytes (32 hex chars) and a span id is 8 bytes (16 hex
chars). They are opaque — never parse meaning out of them.
"""

from __future__ import annotations

import secrets


def new_run_id() -> str:
    """Return a new 32-char hex run id (16 CSPRNG bytes ≈ OTel trace_id)."""
    return secrets.token_hex(16)


def new_span_id() -> str:
    """Return a new 16-char hex span id (8 CSPRNG bytes ≈ OTel span_id)."""
    return secrets.token_hex(8)
