"""Response assembly for the dashboard API.

The DB stores spans flat (each with a ``parent_id``); the UI wants a tree. The
tree builder here is the one non-trivial transform, kept pure and unit-tested.
"""

from __future__ import annotations

from typing import Any, Dict, List

from ..models import Run, Span


def build_span_tree(spans: List[Span]) -> List[Dict[str, Any]]:
    """Turn a flat, start-time-ordered span list into a nested forest.

    Spans whose ``parent_id`` is missing from the set (orphans) are treated as
    roots so nothing is ever dropped from the view.
    """
    nodes: Dict[str, Dict[str, Any]] = {}
    for s in spans:
        node = s.to_dict()
        node["children"] = []
        nodes[s.span_id] = node

    roots: List[Dict[str, Any]] = []
    for s in spans:
        node = nodes[s.span_id]
        parent = nodes.get(s.parent_id) if s.parent_id else None
        if parent is not None:
            parent["children"].append(node)
        else:
            roots.append(node)
    return roots


def run_detail(run: Run, spans: List[Span]) -> Dict[str, Any]:
    """Assemble the full run-detail payload: run, time window, flat spans, tree."""
    starts = [s.start_time for s in spans] or [run.start_time]
    ends = [s.end_time for s in spans if s.end_time is not None]
    window_start = min([run.start_time, *starts])
    window_end = max([run.end_time or window_start, *ends]) if ends else (run.end_time or window_start)

    return {
        "run": run.to_dict(),
        "window": {"start": window_start, "end": window_end},
        "spans": [s.to_dict() for s in spans],
        "tree": build_span_tree(spans),
    }
