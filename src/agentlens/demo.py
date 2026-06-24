"""Generate a realistic sample trace so the dashboard has data immediately.

Used by ``agentlens demo``. Requires **no API keys** — it simulates a small
multi-step research agent (nested LLM + tool calls, with one call that errors)
using short sleeps for lifelike latencies.
"""

from __future__ import annotations

import random
import time

from .models import SpanType
from .spans import span
from .tracer import configure


def _sleep(lo: float, hi: float) -> None:
    time.sleep(random.uniform(lo, hi))


def _one_run(question: str) -> None:
    with span("research_agent", type=SpanType.AGENT_STEP, input={"question": question}) as root:
        # 1. Plan the work with an LLM call.
        with span("plan", type=SpanType.LLM_CALL, model="gpt-4o", input=question) as s:
            _sleep(0.03, 0.08)
            s.set_output("1) search the web  2) do the math  3) write the answer")
            s.set_usage(input_tokens=42, output_tokens=18)

        # 2. A tool call that itself makes a nested LLM call to summarize.
        with span("web_search", type=SpanType.TOOL_CALL, input={"query": question}) as s:
            _sleep(0.05, 0.12)
            hits = ["wiki/agent_systems", "blog/llm_observability", "docs/tracing"]
            s.set_output(hits)
            with span("summarize", type=SpanType.LLM_CALL, model="gpt-4o-mini", input=hits) as s2:
                _sleep(0.02, 0.06)
                s2.set_output("Agent observability means tracing each step of a run.")
                s2.set_usage(input_tokens=120, output_tokens=34)

        # 3. A tool call that errors (caught, so the run still completes).
        try:
            with span("calculator", type=SpanType.TOOL_CALL, input={"expr": "1/0"}):
                _sleep(0.01, 0.03)
                _ = 1 / 0
        except ZeroDivisionError:
            pass

        # 4. Final answer LLM call.
        with span("final_answer", type=SpanType.LLM_CALL, model="gpt-4o", input=question) as s:
            _sleep(0.04, 0.09)
            s.set_output("AgentLens traces every LLM and tool call in your agent run.")
            s.set_usage(input_tokens=200, output_tokens=52)

        root.set_output("done")


def run_demo(db_path: str | None = None, runs: int = 1, seed: int | None = None) -> str:
    """Generate ``runs`` demo runs into the trace DB. Returns the DB path used."""
    if seed is not None:
        random.seed(seed)
    tracer = configure(db_path=db_path)
    questions: list[str] = [
        "What is agent observability and why does it matter?",
        "Summarize the latest on LLM tracing tools.",
        "How many tokens did my last agent run use?",
        "Compare waterfall vs tree views for traces.",
    ]
    for i in range(runs):
        _one_run(questions[i % len(questions)])
    return tracer.config.db_path
