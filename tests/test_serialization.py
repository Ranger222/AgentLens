from __future__ import annotations

import dataclasses

from agentlens.serialization import (
    REDACTED,
    dumps,
    is_secret_key,
    loads,
    to_jsonable,
)


class TestToJsonable:
    def test_primitives_passthrough(self):
        assert to_jsonable(1) == 1
        assert to_jsonable("x") == "x"
        assert to_jsonable(True) is True
        assert to_jsonable(None) is None
        assert to_jsonable(3.5) == 3.5

    def test_collections(self):
        assert to_jsonable((1, 2)) == [1, 2]
        assert sorted(to_jsonable({1, 2})) == [1, 2]
        assert to_jsonable({"a": [1, {"b": 2}]}) == {"a": [1, {"b": 2}]}

    def test_bytes_decoded(self):
        assert to_jsonable(b"hello") == "hello"

    def test_dataclass(self):
        @dataclasses.dataclass
        class P:
            x: int
            y: str

        assert to_jsonable(P(1, "a")) == {"x": 1, "y": "a"}

    def test_pydantic_like_model_dump(self):
        class M:
            def model_dump(self):
                return {"k": "v"}

        assert to_jsonable(M()) == {"k": "v"}

    def test_object_with_to_dict(self):
        class M:
            def to_dict(self):
                return {"a": 1}

        assert to_jsonable(M()) == {"a": 1}

    def test_unserializable_falls_back_to_repr(self):
        class Weird:
            __slots__ = ()

        out = to_jsonable(Weird())
        assert isinstance(out, str) and "Weird" in out

    def test_object_raising_in_repr_is_handled(self):
        class Bad:
            def __repr__(self):
                raise RuntimeError("no repr")

        out = to_jsonable(Bad())
        assert isinstance(out, str)  # never raises

    def test_depth_cap(self):
        d = cur = {}
        for _ in range(50):
            cur["n"] = {}
            cur = cur["n"]
        out = to_jsonable(d)  # must not recurse forever / blow the stack
        assert isinstance(out, dict)

    def test_item_cap(self):
        big = {str(i): i for i in range(5000)}
        out = to_jsonable(big)
        assert len(out) <= 1001  # capped + an overflow marker


class TestRedaction:
    def test_is_secret_key_normalizes(self):
        assert is_secret_key("api_key")
        assert is_secret_key("API-KEY")
        assert is_secret_key("Authorization")
        assert not is_secret_key("model")

    def test_secret_values_redacted(self):
        out = to_jsonable({"api_key": "sk-123", "model": "gpt-4o"})
        assert out["api_key"] == REDACTED
        assert out["model"] == "gpt-4o"

    def test_nested_secret_redacted(self):
        out = to_jsonable({"headers": {"Authorization": "Bearer x"}})
        assert out["headers"]["Authorization"] == REDACTED


class TestDumpsLoads:
    def test_roundtrip(self):
        assert loads(dumps({"a": 1})) == {"a": 1}

    def test_truncation(self):
        out = dumps("x" * 1000, max_len=100)
        assert len(out) <= 100 + len("…[truncated]")
        assert out.endswith("[truncated]")

    def test_loads_tolerates_bad_json(self):
        assert loads(None) is None
        assert loads("{not json") == "{not json"

    def test_dumps_handles_unserializable(self):
        class Weird:
            __slots__ = ()

        # should not raise
        assert isinstance(dumps(Weird()), str)
