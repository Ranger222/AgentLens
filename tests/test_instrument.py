"""Auto-instrumentation tests.

We inject *fake* ``openai`` / ``anthropic`` module trees into ``sys.modules`` so
the real monkeypatch path (patch → call → span; idempotency; uninstrument; async)
is exercised with zero network and zero SDKs installed.
"""

from __future__ import annotations

import sys
import types

import pytest

from agentlens.instrument.anthropic import instrument_anthropic, uninstrument_anthropic
from agentlens.instrument.openai import instrument_openai, uninstrument_openai


# ---------------------------------------------------------------- fake OpenAI
class _OAUsage:
    def __init__(self):
        self.prompt_tokens = 11
        self.completion_tokens = 7
        self.total_tokens = 18


class _OAMessage:
    content = "fake completion"
    tool_calls = None


class _OAChoice:
    message = _OAMessage()


class _OAResp:
    model = "gpt-4o-2024"
    choices = [_OAChoice()]
    usage = _OAUsage()


def _make_fake_openai():
    openai = types.ModuleType("openai")
    resources = types.ModuleType("openai.resources")
    chat = types.ModuleType("openai.resources.chat")
    completions = types.ModuleType("openai.resources.chat.completions")

    class Completions:
        def create(self, **kwargs):
            return _OAResp()

    class AsyncCompletions:
        async def create(self, **kwargs):
            return _OAResp()

    completions.Completions = Completions
    completions.AsyncCompletions = AsyncCompletions
    chat.completions = completions
    resources.chat = chat
    openai.resources = resources

    sys.modules.update(
        {
            "openai": openai,
            "openai.resources": resources,
            "openai.resources.chat": chat,
            "openai.resources.chat.completions": completions,
        }
    )
    return Completions, AsyncCompletions


@pytest.fixture
def fake_openai():
    Completions, AsyncCompletions = _make_fake_openai()
    yield Completions, AsyncCompletions
    uninstrument_openai()
    for m in [
        "openai.resources.chat.completions",
        "openai.resources.chat",
        "openai.resources",
        "openai",
    ]:
        sys.modules.pop(m, None)


# ------------------------------------------------------------- fake Anthropic
class _AntUsage:
    input_tokens = 20
    output_tokens = 9


class _AntBlock:
    text = "claude reply"


class _AntResp:
    model = "claude-3-5-sonnet"
    content = [_AntBlock()]
    usage = _AntUsage()


def _make_fake_anthropic():
    anthropic = types.ModuleType("anthropic")
    resources = types.ModuleType("anthropic.resources")
    messages_mod = types.ModuleType("anthropic.resources.messages")

    class Messages:
        def create(self, **kwargs):
            return _AntResp()

    class AsyncMessages:
        async def create(self, **kwargs):
            return _AntResp()

    messages_mod.Messages = Messages
    messages_mod.AsyncMessages = AsyncMessages
    resources.messages = messages_mod
    anthropic.resources = resources

    sys.modules.update(
        {
            "anthropic": anthropic,
            "anthropic.resources": resources,
            "anthropic.resources.messages": messages_mod,
        }
    )
    return Messages, AsyncMessages


@pytest.fixture
def fake_anthropic():
    Messages, AsyncMessages = _make_fake_anthropic()
    yield Messages, AsyncMessages
    uninstrument_anthropic()
    for m in ["anthropic.resources.messages", "anthropic.resources", "anthropic"]:
        sys.modules.pop(m, None)


def _spans(store):
    return store.get_spans(store.list_runs()[0].run_id)


# ------------------------------------------------------------------ OpenAI
class TestOpenAI:
    def test_records_span_with_normalized_usage(self, store, fake_openai):
        Completions, _ = fake_openai
        instrument_openai()
        Completions().create(model="gpt-4o", messages=[{"role": "user", "content": "hi"}])
        s = _spans(store)[0]
        assert s.type == "llm_call"
        assert s.model == "gpt-4o-2024"  # taken from the response
        assert s.output == "fake completion"
        assert s.usage.input_tokens == 11
        assert s.usage.output_tokens == 7
        assert s.usage.total_tokens == 18
        assert s.metadata.get("provider") == "openai"

    def test_idempotent(self, store, fake_openai):
        Completions, _ = fake_openai
        instrument_openai()
        instrument_openai()  # second call must NOT double-wrap
        Completions().create(model="gpt-4o", messages=[])
        assert len(_spans(store)) == 1  # exactly one span, not two

    def test_uninstrument_restores(self, store, fake_openai):
        Completions, _ = fake_openai
        instrument_openai()
        uninstrument_openai()
        Completions().create(model="gpt-4o", messages=[])
        assert store.count_runs() == 0  # no span recorded after restore

    def test_error_path_reraises(self, store, fake_openai):
        Completions, _ = fake_openai

        def boom(self, **kwargs):
            raise RuntimeError("api down")

        Completions.create = boom
        instrument_openai()
        with pytest.raises(RuntimeError):
            Completions().create(model="gpt-4o", messages=[])
        s = _spans(store)[0]
        assert s.status == "error"
        assert s.error.type == "RuntimeError"

    async def test_async_create(self, store, fake_openai):
        _, AsyncCompletions = fake_openai
        instrument_openai()
        await AsyncCompletions().create(model="gpt-4o", messages=[])
        s = _spans(store)[0]
        assert s.usage.total_tokens == 18

    def test_streaming_marks_metadata(self, store, fake_openai):
        Completions, _ = fake_openai
        instrument_openai()
        Completions().create(model="gpt-4o", messages=[], stream=True)
        s = _spans(store)[0]
        assert s.metadata.get("stream") is True


# ---------------------------------------------------------------- Anthropic
class TestAnthropic:
    def test_records_span(self, store, fake_anthropic):
        Messages, _ = fake_anthropic
        instrument_anthropic()
        Messages().create(model="claude-3-5-sonnet", max_tokens=100, messages=[])
        s = _spans(store)[0]
        assert s.type == "llm_call"
        assert s.output == "claude reply"
        assert s.usage.input_tokens == 20
        assert s.usage.output_tokens == 9
        assert s.usage.total_tokens == 29
        assert s.metadata.get("provider") == "anthropic"

    def test_idempotent_and_uninstrument(self, store, fake_anthropic):
        Messages, _ = fake_anthropic
        instrument_anthropic()
        instrument_anthropic()
        Messages().create(model="c", messages=[])
        assert len(_spans(store)) == 1
        uninstrument_anthropic()
        Messages().create(model="c", messages=[])
        assert len(store.list_runs()) == 1  # no new run after uninstrument

    async def test_async(self, store, fake_anthropic):
        _, AsyncMessages = fake_anthropic
        instrument_anthropic()
        await AsyncMessages().create(model="c", messages=[])
        assert _spans(store)[0].usage.total_tokens == 29


def test_instrument_without_sdk_raises_helpful_error():
    # Simulate the SDK being absent *regardless* of whether it's installed in the
    # test environment (CI installs the extras): setting the module chain to None
    # in sys.modules makes the lazy `import` inside instrument_*() raise, which
    # must surface as a friendly ImportError telling the user what to pip install.
    from unittest import mock

    openai_blocked = dict.fromkeys(
        ["openai", "openai.resources", "openai.resources.chat", "openai.resources.chat.completions"]
    )
    anthropic_blocked = dict.fromkeys(
        ["anthropic", "anthropic.resources", "anthropic.resources.messages"]
    )
    with mock.patch.dict(sys.modules, openai_blocked), pytest.raises(
        ImportError, match="pip install openai"
    ):
        instrument_openai()
    with mock.patch.dict(sys.modules, anthropic_blocked), pytest.raises(
        ImportError, match="pip install anthropic"
    ):
        instrument_anthropic()
