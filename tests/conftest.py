"""Shared pytest fixtures."""

from __future__ import annotations

import pytest

from lenstrace.storage.sqlite import SQLiteStorage
from lenstrace.tracer import configure, shutdown


@pytest.fixture
def store():
    """A global tracer backed by an in-memory SQLite store.

    Reading from the *same* store instance is required because ``:memory:`` DBs
    are per-connection. Yields the store so tests can inspect persisted rows.
    """
    s = SQLiteStorage(":memory:")
    configure(storage=s, enabled=True, capture_io=True)
    yield s
    shutdown()


@pytest.fixture
def only_run(store):
    """Return the single run in the store (asserts exactly one)."""

    def _get():
        runs = store.list_runs()
        assert len(runs) == 1, f"expected 1 run, found {len(runs)}"
        return runs[0]

    return _get
