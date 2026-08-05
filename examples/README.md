# Examples

Runnable examples — **none require an API key**.

## `fake_agent.py`

A fake multi-step "research agent" traced end-to-end. It shows all three
instrumentation styles (`@trace` on functions, `span()` for inline blocks) and a
deliberate error inside one tool, so you immediately get a realistic
nested-with-error trace to explore.

```bash
python examples/fake_agent.py     # writes a trace to ./lenstrace.db
lenstrace serve                   # open http://localhost:8765 and click the run
```

You'll see a `research_agent` run with a `plan` LLM call, a `web_search` tool
that nests a `summarize` LLM call, a `calculator` tool that errors (shown red),
and a `final_answer` LLM call — each with its duration bar and token usage.

> Prefer a one-liner? `lenstrace demo` generates the same kind of trace without
> running a script.

## Tracing real OpenAI / Anthropic calls

Install the SDK you use and turn on auto-instrumentation — every model call
becomes an `llm_call` span automatically:

```python
import lenstrace
from openai import OpenAI

lenstrace.instrument_openai()
client = OpenAI()
client.chat.completions.create(model="gpt-4o", messages=[{"role": "user", "content": "hi"}])
# → one llm_call span with model, messages, output, and token usage
```

(`lenstrace.instrument_anthropic()` does the same for the Anthropic SDK.)
