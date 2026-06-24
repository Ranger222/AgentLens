from __future__ import annotations

import re

from agentlens.ids import new_run_id, new_span_id

_HEX = re.compile(r"^[0-9a-f]+$")


def test_run_id_is_32_hex_chars():
    rid = new_run_id()
    assert len(rid) == 32
    assert _HEX.match(rid)


def test_span_id_is_16_hex_chars():
    sid = new_span_id()
    assert len(sid) == 16
    assert _HEX.match(sid)


def test_ids_are_unique():
    assert len({new_run_id() for _ in range(1000)}) == 1000
    assert len({new_span_id() for _ in range(1000)}) == 1000


def test_ids_are_never_all_zero():
    # OTel treats an all-zero id as invalid; CSPRNG makes this ~impossible.
    for _ in range(100):
        assert set(new_run_id()) != {"0"}
        assert set(new_span_id()) != {"0"}
