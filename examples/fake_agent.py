"""A fake multi-step "research agent" traced end-to-end with LensTrace.

Runs with **zero API keys** — the "LLM" is simulated. It shows all three
instrumentation styles:

  * ``@trace``      on whole functions (agent steps / tools)
  * ``span(...)``   context manager for inline blocks (the fake LLM calls)
  * a deliberate error inside one tool, captured and shown in the timeline

Run it, then view the trace::

    python examples/fake_agent.py
    lenstrace serve
"""

from __future__ import annotations

import random
import time

from lenstrace import configure, span, trace
from lenstrace.models import SpanType


def fake_llm(prompt: str, *, model: str = "gpt-4o") -> str:
    """Pretend to call an LLM. Records an ``llm_call`` span with token usage."""
    with span(f"llm:{model}", type=SpanType.LLM_CALL, model=model, input=prompt) as s:
        time.sleep(random.uniform(0.02, 0.07))
        completion = f"(fake answer to: {prompt[:48]}…)"
        s.set_output(completion)
        s.set_usage(input_tokens=8 + len(prompt.split()), output_tokens=14)
        return completion


@trace(type=SpanType.TOOL_CALL)
def web_search(query: str) -> list[str]:
    """A tool that 'searches the web' and then summarizes hits with the LLM."""
    time.sleep(random.uniform(0.03, 0.09))
    hits = [f"result:{query[:12]}:{i}" for i in range(3)]
    fake_llm(f"Summarize these search hits: {hits}", model="gpt-4o-mini")
    return hits


@trace(type=SpanType.TOOL_CALL)
def calculator(expression: str) -> float:
    """A tool that evaluates math — and blows up on a divide-by-zero on purpose."""
    time.sleep(random.uniform(0.005, 0.02))
    return eval(expression)  # noqa: S307 - intentional, for the demo error case


@trace(name="research_agent", type=SpanType.AGENT_STEP)
def research_agent(question: str) -> str:
    """Top-level agent: plan → search → (failing) calc → final answer."""
    fake_llm(f"Plan how to answer: {question}", model="gpt-4o")
    web_search(question)

    # This tool call errors; we catch it so the run still finishes, and the
    # error shows up red in the timeline.
    try:
        calculator("1 / 0")
    except ZeroDivisionError:
        pass

    return fake_llm(f"Write the final answer to: {question}")


if __name__ == "__main__":
    db_path = configure().config.db_path
    question = "What is LLM-agent observability and why does it matter?"
    answer = research_agent(question)
    print(f"Agent answered: {answer}")
    print(f"\nTrace written to: {db_path}")
    print("View it with:     lenstrace serve")
