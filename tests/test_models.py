from __future__ import annotations

from lenstrace.models import ErrorInfo, Run, RunSummary, Span, SpanStatus, SpanType, TokenUsage


class TestTokenUsage:
    def test_total_is_derived_when_absent(self):
        u = TokenUsage(input_tokens=10, output_tokens=5)
        assert u.total_tokens == 15

    def test_total_is_respected_when_given(self):
        u = TokenUsage(input_tokens=10, output_tokens=5, total_tokens=99)
        assert u.total_tokens == 99

    def test_total_not_derived_when_one_side_missing(self):
        assert TokenUsage(input_tokens=10).total_tokens is None

    def test_is_empty(self):
        assert TokenUsage().is_empty()
        assert not TokenUsage(input_tokens=1).is_empty()

    def test_from_dict_roundtrip(self):
        d = TokenUsage(1, 2).to_dict()
        assert TokenUsage.from_dict(d).total_tokens == 3
        assert TokenUsage.from_dict(None) is None


class TestErrorInfo:
    def test_from_exception(self):
        try:
            raise ValueError("boom")
        except ValueError as e:
            info = ErrorInfo.from_exception(e, "TB")
        assert info.type == "ValueError"
        assert info.message == "boom"
        assert info.traceback == "TB"

    def test_from_dict(self):
        assert ErrorInfo.from_dict(None) is None
        info = ErrorInfo.from_dict({"type": "X", "message": "m"})
        assert info.type == "X" and info.message == "m"


class TestSpan:
    def test_duration_ms(self):
        s = Span(span_id="a", run_id="r", name="x", start_time=100.0, end_time=100.5)
        assert s.duration_ms == 500.0

    def test_duration_none_when_running(self):
        s = Span(span_id="a", run_id="r", name="x", start_time=100.0)
        assert s.duration_ms is None

    def test_duration_never_negative(self):
        s = Span(span_id="a", run_id="r", name="x", start_time=100.0, end_time=99.0)
        assert s.duration_ms == 0.0

    def test_is_error(self):
        s = Span(span_id="a", run_id="r", name="x", status=SpanStatus.ERROR)
        assert s.is_error

    def test_setters_are_chainable(self):
        s = Span(span_id="a", run_id="r", name="x")
        out = s.set_output("o").set_usage(1, 2).set_model("gpt-4o").set_metadata(k="v")
        assert out is s
        assert s.output == "o"
        assert s.usage.total_tokens == 3
        assert s.model == "gpt-4o"
        assert s.metadata == {"k": "v"}

    def test_record_error_sets_status(self):
        s = Span(span_id="a", run_id="r", name="x")
        s.record_error(ValueError("nope"))
        assert s.status == SpanStatus.ERROR
        assert s.error.type == "ValueError"

    def test_to_dict_shape(self):
        s = Span(span_id="a", run_id="r", name="x", type=SpanType.LLM_CALL, start_time=1.0, end_time=2.0)
        d = s.to_dict()
        assert d["duration_ms"] == 1000.0
        assert set(d) >= {"span_id", "run_id", "parent_id", "type", "status", "duration_ms"}


class TestRunSummary:
    def test_to_dict_includes_models(self):
        rs = RunSummary(
            run_id="r", name="n", start_time=1.0, end_time=2.0,
            status=SpanStatus.OK, span_count=3, models={"gpt-4o": 2},
        )
        d = rs.to_dict()
        assert d["models"] == {"gpt-4o": 2}
        assert d["duration_ms"] == 1000.0


class TestRun:
    def test_duration(self):
        r = Run(run_id="r", start_time=10.0, end_time=11.5)
        assert r.duration_ms == 1500.0
