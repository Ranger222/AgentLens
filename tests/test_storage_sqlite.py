from __future__ import annotations

import time

from agentlens.models import ErrorInfo, Run, Span, SpanStatus, SpanType, TokenUsage
from agentlens.storage.sqlite import SQLiteStorage, _count_models


def _run(rid="r1", **kw):
    return Run(run_id=rid, name=kw.get("name", "run"), start_time=kw.get("start", time.time()),
               status=kw.get("status", SpanStatus.OK), end_time=kw.get("end"))


def _span(sid, rid="r1", **kw):
    return Span(
        span_id=sid, run_id=rid, name=kw.get("name", sid), type=kw.get("type", SpanType.AGENT_STEP),
        parent_id=kw.get("parent"), start_time=kw.get("start", time.time()),
        end_time=kw.get("end"), status=kw.get("status", SpanStatus.OK),
        input=kw.get("input"), output=kw.get("output"), error=kw.get("error"),
        usage=kw.get("usage"), model=kw.get("model"),
    )


class TestRunCrud:
    def test_save_and_get_run(self):
        s = SQLiteStorage(":memory:")
        s.save_run(_run(name="hello", start=1.0, end=2.0))
        got = s.get_run("r1")
        assert got is not None
        assert got.name == "hello"
        assert got.duration_ms == 1000.0

    def test_get_missing_run(self):
        assert SQLiteStorage(":memory:").get_run("nope") is None

    def test_count_runs(self):
        s = SQLiteStorage(":memory:")
        assert s.count_runs() == 0
        s.save_run(_run("a"))
        s.save_run(_run("b"))
        assert s.count_runs() == 2

    def test_delete_run_cascades(self):
        s = SQLiteStorage(":memory:")
        s.save_run(_run())
        s.save_span(_span("s1"))
        assert s.delete_run("r1") is True
        assert s.get_run("r1") is None
        assert s.get_spans("r1") == []
        assert s.delete_run("r1") is False


class TestSpanCrud:
    def test_save_and_get_spans_with_io(self):
        s = SQLiteStorage(":memory:")
        s.save_run(_run())
        s.save_span(_span("s1", input={"q": "hi"}, output=[1, 2], model="gpt-4o",
                          usage=TokenUsage(3, 4)))
        spans = s.get_spans("r1")
        assert len(spans) == 1
        sp = spans[0]
        assert sp.input == {"q": "hi"}  # JSON round-trips back to a dict
        assert sp.output == [1, 2]
        assert sp.usage.total_tokens == 7
        assert sp.model == "gpt-4o"

    def test_error_roundtrip(self):
        s = SQLiteStorage(":memory:")
        s.save_run(_run())
        s.save_span(_span("s1", status=SpanStatus.ERROR,
                          error=ErrorInfo("ValueError", "boom", "tb")))
        sp = s.get_spans("r1")[0]
        assert sp.error.type == "ValueError"
        assert sp.error.message == "boom"

    def test_seq_increments_per_run(self):
        s = SQLiteStorage(":memory:")
        s.save_run(_run())
        for i in range(5):
            s.save_span(_span(f"s{i}"))
        seqs = [sp.seq for sp in s.get_spans("r1")]
        assert seqs == [0, 1, 2, 3, 4]

    def test_ordering_by_start_then_seq(self):
        s = SQLiteStorage(":memory:")
        s.save_run(_run())
        # same start_time -> seq decides order
        s.save_span(_span("a", start=100.0))
        s.save_span(_span("b", start=100.0))
        s.save_span(_span("c", start=99.0))  # earlier start sorts first
        order = [sp.span_id for sp in s.get_spans("r1")]
        assert order == ["c", "a", "b"]

    def test_get_span_single(self):
        s = SQLiteStorage(":memory:")
        s.save_run(_run())
        s.save_span(_span("s1"))
        assert s.get_span("r1", "s1").span_id == "s1"
        assert s.get_span("r1", "missing") is None

    def test_update_span(self):
        s = SQLiteStorage(":memory:")
        s.save_run(_run())
        sp = _span("s1")
        s.save_span(sp)
        sp.end_time = sp.start_time + 1
        sp.status = SpanStatus.OK
        sp.output = "done"
        s.update_span(sp)
        assert s.get_spans("r1")[0].output == "done"

    def test_seq_cold_start_continues_from_disk(self, tmp_path):
        db = str(tmp_path / "t.db")
        s1 = SQLiteStorage(db)
        s1.save_run(_run())
        s1.save_span(_span("s0"))
        s1.save_span(_span("s1"))
        s1.close()
        # New process/connection: counter is cold; must continue at 2, not reset.
        s2 = SQLiteStorage(db)
        s2.save_span(_span("s2"))
        assert s2.get_span("r1", "s2").seq == 2


class TestListRunsRollups:
    def test_rollups(self):
        s = SQLiteStorage(":memory:")
        s.save_run(_run())
        s.save_span(_span("root"))
        s.save_span(_span("a", type=SpanType.LLM_CALL, model="gpt-4o", usage=TokenUsage(10, 5)))
        s.save_span(_span("b", type=SpanType.LLM_CALL, model="gpt-4o", usage=TokenUsage(1, 1)))
        s.save_span(_span("c", status=SpanStatus.ERROR))
        summary = s.list_runs()[0]
        assert summary.span_count == 4
        assert summary.error_count == 1
        assert summary.total_tokens == 17
        assert summary.models == {"gpt-4o": 2}

    def test_newest_first(self):
        s = SQLiteStorage(":memory:")
        s.save_run(_run("old", start=1.0))
        s.save_run(_run("new", start=2.0))
        ids = [r.run_id for r in s.list_runs()]
        assert ids == ["new", "old"]

    def test_pagination(self):
        s = SQLiteStorage(":memory:")
        for i in range(5):
            s.save_run(_run(f"r{i}", start=float(i)))
        page = s.list_runs(limit=2, offset=0)
        assert len(page) == 2


def test_count_models_helper():
    assert _count_models(None) == {}
    assert _count_models("gpt-4o,gpt-4o,claude") == {"gpt-4o": 2, "claude": 1}
