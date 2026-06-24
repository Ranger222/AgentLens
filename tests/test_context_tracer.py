"""Parent/child correctness — the highest-value tests. A misleading tree is
worse than no tracing, so we pin nesting across sync, async, and threads."""

from __future__ import annotations

import asyncio
import threading

from agentlens import TracedThreadPoolExecutor, span
from agentlens.context import current_run, current_span


def _spans(store):
    run = store.list_runs()[0]
    return run, store.get_spans(run.run_id)


def _by_name(spans):
    return {s.name: s for s in spans}


def test_flat_spans_share_root_run(store):
    with span("root"):
        with span("a"):
            pass
        with span("b"):
            pass
    run, spans = _spans(store)
    names = _by_name(spans)
    root = names["root"]
    assert root.parent_id is None
    assert names["a"].parent_id == root.span_id
    assert names["b"].parent_id == root.span_id
    assert run.span_count == 3


def test_deep_nesting(store):
    with span("l0"), span("l1"), span("l2"):
        pass
    _, spans = _spans(store)
    n = _by_name(spans)
    assert n["l1"].parent_id == n["l0"].span_id
    assert n["l2"].parent_id == n["l1"].span_id


def test_context_is_cleared_after_run(store):
    with span("root"):
        assert current_span() is not None
        assert current_run() is not None
    assert current_span() is None
    assert current_run() is None


def test_sibling_spans_do_not_nest(store):
    with span("root"):
        with span("a"):
            pass
        # 'b' must attach to root, not to the already-closed 'a'
        with span("b"):
            pass
    _, spans = _spans(store)
    n = _by_name(spans)
    assert n["a"].parent_id == n["root"].span_id
    assert n["b"].parent_id == n["root"].span_id


def test_run_status_rolls_up_error(store):
    with span("root"):
        try:
            with span("bad"):
                raise ValueError("x")
        except ValueError:
            pass
    run, _ = _spans(store)
    assert run.status == "error"
    assert run.error_count == 1


def test_duration_is_non_negative_and_monotonic(store):
    with span("root"):
        pass
    _, spans = _spans(store)
    root = spans[0]
    assert root.end_time >= root.start_time
    assert root.duration_ms is not None and root.duration_ms >= 0


class TestAsyncNesting:
    async def test_async_gather_siblings_attach_to_parent(self, store):
        async def child(i):
            with span(f"child{i}", type="tool_call"):
                await asyncio.sleep(0.001)

        with span("root"):
            await asyncio.gather(child(0), child(1), child(2))

        _, spans = _spans(store)
        n = _by_name(spans)
        root = n["root"]
        for i in range(3):
            assert n[f"child{i}"].parent_id == root.span_id, f"child{i} misparented"

    async def test_concurrent_tasks_do_not_cross_link(self, store):
        async def branch(label):
            with span(f"{label}-outer"):
                await asyncio.sleep(0.001)
                with span(f"{label}-inner"):
                    await asyncio.sleep(0.001)

        with span("root"):
            await asyncio.gather(branch("A"), branch("B"))

        _, spans = _spans(store)
        n = _by_name(spans)
        # Each inner must nest under ITS OWN outer, not the other branch's.
        assert n["A-inner"].parent_id == n["A-outer"].span_id
        assert n["B-inner"].parent_id == n["B-outer"].span_id


class TestThreadNesting:
    def test_traced_pool_reattaches_to_parent(self, store):
        def worker(i):
            with span(f"w{i}", type="tool_call"):
                return i

        with span("root"), TracedThreadPoolExecutor(max_workers=4) as pool:
            list(pool.map(lambda i: worker(i), range(4)))

        _, spans = _spans(store)
        n = _by_name(spans)
        root = n["root"]
        for i in range(4):
            assert n[f"w{i}"].parent_id == root.span_id

    def test_raw_thread_detaches_into_own_run(self, store):
        # Documents the known limitation: a raw thread starts with empty
        # context, so its span becomes a new top-level root (own run).
        def worker():
            with span("threaded", type="tool_call"):
                pass

        with span("root"):
            t = threading.Thread(target=worker)
            t.start()
            t.join()

        runs = store.list_runs()
        # Two runs: the main 'root' run and the detached 'threaded' run.
        assert len(runs) == 2
