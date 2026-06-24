"""Core data model: spans, runs, token usage, errors.

The model is intentionally small and stdlib-only (dataclasses), so importing it
for tracing pulls in no third-party dependencies. It is loosely compatible with
OpenTelemetry concepts (a *run* ≈ a trace, spans nest via ``parent_id``) without
taking an OTel dependency.
"""

from __future__ import annotations

import dataclasses
from dataclasses import dataclass, field
from typing import Any


class SpanType(str):
    """String-enum of span types.

    Subclassing ``str`` keeps values JSON/SQLite-friendly and comparable to
    plain strings, while the constants document the supported set. Unknown
    custom strings are still accepted (the SDK never rejects a user's type).
    """

    LLM_CALL = "llm_call"
    TOOL_CALL = "tool_call"
    AGENT_STEP = "agent_step"
    CHAIN = "chain"
    RETRIEVAL = "retrieval"
    CUSTOM = "custom"


class SpanStatus(str):
    """Lifecycle/outcome status of a span or run."""

    RUNNING = "running"
    OK = "ok"
    ERROR = "error"


@dataclass
class TokenUsage:
    """LLM token accounting. All fields optional; ``total`` is derived if absent."""

    input_tokens: int | None = None
    output_tokens: int | None = None
    total_tokens: int | None = None

    def __post_init__(self) -> None:
        if (
            self.total_tokens is None
            and self.input_tokens is not None
            and self.output_tokens is not None
        ):
            self.total_tokens = self.input_tokens + self.output_tokens

    def is_empty(self) -> bool:
        return (
            self.input_tokens is None
            and self.output_tokens is None
            and self.total_tokens is None
        )

    def to_dict(self) -> dict[str, Any]:
        return dataclasses.asdict(self)

    @classmethod
    def from_dict(cls, d: dict[str, Any] | None) -> TokenUsage | None:
        if not d:
            return None
        return cls(
            input_tokens=d.get("input_tokens"),
            output_tokens=d.get("output_tokens"),
            total_tokens=d.get("total_tokens"),
        )


@dataclass
class ErrorInfo:
    """A captured exception: type name, message, and formatted traceback."""

    type: str
    message: str
    traceback: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return dataclasses.asdict(self)

    @classmethod
    def from_dict(cls, d: dict[str, Any] | None) -> ErrorInfo | None:
        if not d:
            return None
        return cls(
            type=d.get("type", "Error"),
            message=d.get("message", ""),
            traceback=d.get("traceback"),
        )

    @classmethod
    def from_exception(cls, exc: BaseException, tb: str | None = None) -> ErrorInfo:
        return cls(type=type(exc).__name__, message=str(exc), traceback=tb)


@dataclass
class Span:
    """A single unit of work within a run.

    Times are epoch seconds (float). ``end_time`` is computed from a monotonic
    clock delta added to the wall-clock ``start_time`` so that duration is
    accurate and ``end_time >= start_time`` even if the system clock shifts.
    """

    span_id: str
    run_id: str
    name: str
    type: str = SpanType.AGENT_STEP
    parent_id: str | None = None
    start_time: float = 0.0
    end_time: float | None = None
    status: str = SpanStatus.RUNNING
    input: Any = None
    output: Any = None
    error: ErrorInfo | None = None
    usage: TokenUsage | None = None
    model: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    # Monotonic insertion order within a run; used as a stable tiebreaker when
    # sibling spans share a start_time. Set by the storage layer on insert.
    seq: int = 0

    @property
    def duration_ms(self) -> float | None:
        if self.end_time is None:
            return None
        return max(0.0, (self.end_time - self.start_time) * 1000.0)

    @property
    def is_error(self) -> bool:
        return self.status == SpanStatus.ERROR

    # -- ergonomic setters (chainable) used by the context-manager / manual API
    def set_input(self, value: Any) -> Span:
        self.input = value
        return self

    def set_output(self, value: Any) -> Span:
        self.output = value
        return self

    def set_model(self, model: str | None) -> Span:
        self.model = model
        return self

    def set_usage(
        self,
        input_tokens: int | None = None,
        output_tokens: int | None = None,
        total_tokens: int | None = None,
    ) -> Span:
        self.usage = TokenUsage(
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=total_tokens,
        )
        return self

    def set_metadata(self, **kwargs: Any) -> Span:
        self.metadata.update(kwargs)
        return self

    def record_error(self, exc: BaseException, traceback_str: str | None = None) -> Span:
        self.error = ErrorInfo.from_exception(exc, traceback_str)
        self.status = SpanStatus.ERROR
        return self

    def to_dict(self) -> dict[str, Any]:
        return {
            "span_id": self.span_id,
            "run_id": self.run_id,
            "name": self.name,
            "type": self.type,
            "parent_id": self.parent_id,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "duration_ms": self.duration_ms,
            "status": self.status,
            "input": self.input,
            "output": self.output,
            "error": self.error.to_dict() if self.error else None,
            "usage": self.usage.to_dict() if self.usage else None,
            "model": self.model,
            "metadata": self.metadata,
            "seq": self.seq,
        }


@dataclass
class Run:
    """A top-level grouping of spans — one agent execution / session."""

    run_id: str
    name: str | None = None
    start_time: float = 0.0
    end_time: float | None = None
    status: str = SpanStatus.RUNNING
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def duration_ms(self) -> float | None:
        if self.end_time is None:
            return None
        return max(0.0, (self.end_time - self.start_time) * 1000.0)

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "name": self.name,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "duration_ms": self.duration_ms,
            "status": self.status,
            "metadata": self.metadata,
        }


@dataclass
class RunSummary:
    """Lightweight run row for the runs list (no spans), plus rollups."""

    run_id: str
    name: str | None
    start_time: float
    end_time: float | None
    status: str
    span_count: int = 0
    error_count: int = 0
    total_tokens: int | None = None
    models: dict[str, int] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def duration_ms(self) -> float | None:
        if self.end_time is None:
            return None
        return max(0.0, (self.end_time - self.start_time) * 1000.0)

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "name": self.name,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "duration_ms": self.duration_ms,
            "status": self.status,
            "span_count": self.span_count,
            "error_count": self.error_count,
            "total_tokens": self.total_tokens,
            "models": self.models,
            "metadata": self.metadata,
        }
