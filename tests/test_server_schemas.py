from __future__ import annotations

from agentlens.models import Run, Span, SpanStatus
from agentlens.server.schemas import build_span_tree, run_detail


def _s(sid, parent=None, start=0.0, end=1.0):
    return Span(span_id=sid, run_id="r", name=sid, parent_id=parent, start_time=start, end_time=end)


def test_build_tree_nests_children():
    spans = [_s("root"), _s("a", "root"), _s("a1", "a"), _s("b", "root")]
    tree = build_span_tree(spans)
    assert len(tree) == 1
    root = tree[0]
    assert {c["span_id"] for c in root["children"]} == {"a", "b"}
    a = next(c for c in root["children"] if c["span_id"] == "a")
    assert a["children"][0]["span_id"] == "a1"


def test_orphan_span_becomes_root():
    # parent_id points at a span not in the set -> treated as a root, never dropped
    spans = [_s("root"), _s("orphan", "missing-parent")]
    tree = build_span_tree(spans)
    ids = {n["span_id"] for n in tree}
    assert ids == {"root", "orphan"}


def test_empty():
    assert build_span_tree([]) == []


def test_run_detail_window_covers_all_spans():
    run = Run(run_id="r", name="n", start_time=100.0, end_time=105.0, status=SpanStatus.OK)
    spans = [_s("a", start=100.0, end=102.0), _s("b", start=101.0, end=104.5)]
    detail = run_detail(run, spans)
    assert detail["window"]["start"] <= 100.0
    assert detail["window"]["end"] >= 104.5
    assert len(detail["spans"]) == 2
    assert len(detail["tree"]) == 2
