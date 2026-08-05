"""Concurrency helpers for correct span nesting across threads.

``contextvars`` do **not** propagate into worker threads: a span started in a
worker would detach (``parent_id=None``) and flatten the tree. ``asyncio`` is
fine (a Task copies context at creation), but raw threads and
``loop.run_in_executor`` are not. ``TracedThreadPoolExecutor`` copies the
submitting context into each worker so nesting is preserved.
"""

from __future__ import annotations

import contextvars
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Callable, TypeVar

R = TypeVar("R")


class TracedThreadPoolExecutor(ThreadPoolExecutor):
    """Drop-in ``ThreadPoolExecutor`` that propagates the active span context.

    Use it exactly like the stdlib executor::

        from lenstrace import TracedThreadPoolExecutor

        with TracedThreadPoolExecutor() as pool:
            pool.submit(traced_worker, arg)   # nests under the current span
    """

    def submit(self, fn: Callable[..., R], /, *args: Any, **kwargs: Any) -> Any:
        ctx = contextvars.copy_context()

        def _run() -> R:
            return ctx.run(fn, *args, **kwargs)

        return super().submit(_run)
