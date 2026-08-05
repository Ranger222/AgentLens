from __future__ import annotations

import asyncio

import pytest

from lenstrace import trace
from lenstrace.models import SpanType


def _only_span(store):
    run = store.list_runs()[0]
    spans = store.get_spans(run.run_id)
    assert len(spans) == 1
    return spans[0]


class TestSyncDecorator:
    def test_bare_decorator(self, store):
        @trace
        def f(x):
            return x * 2

        assert f(3) == 6
        s = _only_span(store)
        assert s.name.endswith("f")
        assert s.type == SpanType.AGENT_STEP
        assert s.status == "ok"

    def test_parametrized_decorator(self, store):
        @trace(name="custom", type=SpanType.TOOL_CALL)
        def f():
            return 1

        f()
        s = _only_span(store)
        assert s.name == "custom"
        assert s.type == SpanType.TOOL_CALL

    def test_captures_named_input_and_output(self, store):
        @trace
        def add(a, b):
            return a + b

        add(2, b=5)
        s = _only_span(store)
        assert s.input == {"a": 2, "b": 5}
        assert s.output == 7

    def test_self_is_stripped_from_input(self, store):
        class Agent:
            @trace
            def run(self, q):
                return q

        Agent().run("hi")
        s = _only_span(store)
        assert "self" not in s.input
        assert s.input == {"q": "hi"}

    def test_capture_toggles(self, store):
        @trace(capture_input=False, capture_output=False)
        def f(secret):
            return secret

        f("xyz")
        s = _only_span(store)
        assert s.input is None
        assert s.output is None

    def test_exception_recorded_and_reraised(self, store):
        @trace
        def boom():
            raise ValueError("nope")

        with pytest.raises(ValueError, match="nope"):
            boom()
        s = _only_span(store)
        assert s.status == "error"
        assert s.error.type == "ValueError"
        assert "nope" in s.error.message
        assert s.error.traceback and "ValueError" in s.error.traceback

    def test_preserves_function_metadata(self, store):
        @trace
        def documented():
            """my docstring"""

        assert documented.__name__ == "documented"
        assert documented.__doc__ == "my docstring"


class TestAsyncDecorator:
    async def test_async_function(self, store):
        @trace
        async def f(x):
            await asyncio.sleep(0.001)
            return x + 1

        assert await f(1) == 2
        s = _only_span(store)
        assert s.status == "ok"
        assert s.output == 2

    async def test_async_exception(self, store):
        @trace
        async def boom():
            raise RuntimeError("async boom")

        with pytest.raises(RuntimeError):
            await boom()
        s = _only_span(store)
        assert s.status == "error"
        assert s.error.type == "RuntimeError"


class TestGeneratorDecorator:
    def test_sync_generator_span_covers_whole_iteration(self, store):
        order = []

        @trace
        def gen():
            for i in range(3):
                order.append(i)
                yield i

        result = list(gen())
        assert result == [0, 1, 2]
        s = _only_span(store)
        assert s.status == "ok"
        # span ends only after the generator is exhausted
        assert s.end_time is not None

    def test_sync_generator_closes_on_early_break(self, store):
        @trace
        def gen():
            yield 1
            yield 2
            yield 3

        for v in gen():
            if v == 1:
                break  # triggers GeneratorExit -> span must still close
        s = _only_span(store)
        assert s.end_time is not None

    def test_generator_exception(self, store):
        @trace
        def gen():
            yield 1
            raise ValueError("gen boom")

        with pytest.raises(ValueError):
            list(gen())
        s = _only_span(store)
        assert s.status == "error"

    async def test_async_generator(self, store):
        @trace
        async def agen():
            for i in range(3):
                await asyncio.sleep(0.001)
                yield i

        out = [x async for x in agen()]
        assert out == [0, 1, 2]
        s = _only_span(store)
        assert s.status == "ok"


class TestFailSilent:
    def test_storage_failure_does_not_break_user_code(self, store, monkeypatch):
        # Make every persistence call raise; the decorated function must still
        # return its value (tracing degrades, app survives).
        monkeypatch.setattr(store, "save_span", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("db down")))
        monkeypatch.setattr(store, "save_run", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("db down")))

        @trace
        def f():
            return "ok"

        assert f() == "ok"

    def test_disabled_tracer_runs_user_code_without_spans(self):
        from lenstrace.storage.sqlite import SQLiteStorage
        from lenstrace.tracer import configure, shutdown

        s = SQLiteStorage(":memory:")
        configure(storage=s, enabled=False)

        @trace
        def f(x):
            return x

        assert f(5) == 5
        assert s.count_runs() == 0
        shutdown()
