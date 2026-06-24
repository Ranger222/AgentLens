from __future__ import annotations

import pytest

from agentlens import end_span, run, span, start_span
from agentlens.models import SpanType
from agentlens.storage.sqlite import SQLiteStorage
from agentlens.tracer import configure, shutdown


class TestSpanContextManager:
    def test_records_output_and_usage(self, store):
        with span("search", type=SpanType.TOOL_CALL, input="q") as s:
            s.set_output(["a", "b"])
            s.set_usage(input_tokens=3, output_tokens=4)
        rec = store.get_spans(store.list_runs()[0].run_id)[0]
        assert rec.input == "q"
        assert rec.output == ["a", "b"]
        assert rec.usage.total_tokens == 7
        assert rec.type == SpanType.TOOL_CALL

    def test_exception_recorded_and_reraised(self, store):
        with pytest.raises(ValueError), span("boom"):
            raise ValueError("x")
        rec = store.get_spans(store.list_runs()[0].run_id)[0]
        assert rec.status == "error"
        assert rec.error.type == "ValueError"

    def test_model_passed_through(self, store):
        with span("llm", type=SpanType.LLM_CALL, model="gpt-4o"):
            pass
        rec = store.get_spans(store.list_runs()[0].run_id)[0]
        assert rec.model == "gpt-4o"


class TestRunContextManager:
    def test_groups_multiple_top_level_spans(self, store):
        with run("batch"):
            with span("a"):
                pass
            with span("b"):
                pass
        runs = store.list_runs()
        assert len(runs) == 1
        assert runs[0].name == "batch"
        assert runs[0].span_count == 2

    def test_run_error_rollup(self, store):
        with run("batch"):
            try:
                with span("bad"):
                    raise ValueError("x")
            except ValueError:
                pass
        assert store.list_runs()[0].status == "error"

    def test_run_exception_marks_error_and_reraises(self, store):
        with pytest.raises(RuntimeError), run("batch"):
            with span("a"):
                pass
            raise RuntimeError("boom")
        assert store.list_runs()[0].status == "error"


class TestManualApi:
    def test_start_and_end(self, store):
        s = start_span("manual", type=SpanType.TOOL_CALL, input={"x": 1})
        s.set_output("done")
        end_span(s, usage=None)
        rec = store.get_spans(store.list_runs()[0].run_id)[0]
        assert rec.name == "manual"
        assert rec.output == "done"

    def test_manual_error(self, store):
        s = start_span("manual")
        try:
            raise ValueError("e")
        except ValueError as e:
            end_span(s, error=e)
        rec = store.get_spans(store.list_runs()[0].run_id)[0]
        assert rec.status == "error"


class TestDisabled:
    def test_span_is_noop_but_yields_usable_handle(self):
        s = SQLiteStorage(":memory:")
        configure(storage=s, enabled=False)
        with span("x") as sp:
            sp.set_output("y")  # must not raise even though detached
        assert s.count_runs() == 0
        shutdown()

    def test_run_is_noop(self):
        s = SQLiteStorage(":memory:")
        configure(storage=s, enabled=False)
        with run("x") as r:
            assert r is None
        assert s.count_runs() == 0
        shutdown()
