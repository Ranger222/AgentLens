"""Abstract storage interface.

Keeping this an ABC (rather than baking SQLite into the tracer) means alternate
backends — an in-memory store for tests, or a future Postgres exporter — can be
dropped in without touching the SDK core.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import List, Optional

from ..models import Run, RunSummary, Span


class Storage(ABC):
    @abstractmethod
    def save_run(self, run: Run) -> None:
        """Insert (or upsert) a run row."""

    @abstractmethod
    def update_run(self, run: Run) -> None:
        """Update a run's mutable fields (end_time, status, metadata)."""

    @abstractmethod
    def save_span(self, span: Span) -> None:
        """Insert a span. Assigns ``span.seq`` (per-run insertion order)."""

    @abstractmethod
    def update_span(self, span: Span) -> None:
        """Update a span's mutable fields on completion."""

    @abstractmethod
    def list_runs(self, *, limit: int = 50, offset: int = 0) -> List[RunSummary]:
        """Return run summaries, newest first, with span/error/token rollups."""

    @abstractmethod
    def get_run(self, run_id: str) -> Optional[Run]:
        """Return a single run, or ``None`` if not found."""

    @abstractmethod
    def get_spans(self, run_id: str) -> List[Span]:
        """Return all spans for a run, ordered by (start_time, seq)."""

    @abstractmethod
    def get_span(self, run_id: str, span_id: str) -> Optional[Span]:
        """Return a single span within a run, or ``None``."""

    @abstractmethod
    def delete_run(self, run_id: str) -> bool:
        """Delete a run and its spans. Returns True if the run existed."""

    @abstractmethod
    def count_runs(self) -> int:
        """Total number of runs."""

    def close(self) -> None:  # pragma: no cover - default no-op
        """Release any resources. Safe to call multiple times."""
