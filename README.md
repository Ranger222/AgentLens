<div align="center">

# 🔍 AgentLens

### Chrome DevTools for your AI agents — fully local, zero external dependencies.

*Instrument your Python LLM agents and see every LLM call, tool call, token count, latency, and error as a collapsible timeline.*

</div>

> [!NOTE]
> **Status: under active construction.** This README is being filled in as the
> project is built out. See [docs/](docs/) for the design and
> [docs/ROADMAP.md](docs/ROADMAP.md) for what's landing.

---

AgentLens is an MIT-licensed, open-source observability/tracing tool for
multi-agent and LLM-agent systems in Python. Add a decorator, run your agent,
and open a local dashboard that shows exactly what happened inside the run —
the way Chrome DevTools shows you what happened inside a page load.

- **Frictionless SDK** — a `@trace` decorator, a `span()` context manager, and a
  manual span API. Framework-agnostic, with example auto-instrumentation for the
  raw OpenAI / Anthropic SDKs.
- **Local-first** — traces are stored in SQLite. No accounts, no cloud, no keys.
- **Readable dashboard** — a FastAPI + React (Vite) UI that lists runs and shows
  a single run as a collapsible timeline/tree, dark-mode friendly. One command
  to launch.

## Quickstart (coming together)

```bash
pip install agentlens          # 1. install
agentlens demo                 # 2. generate a sample trace (no API keys needed)
agentlens serve                # 3. open the dashboard at http://localhost:4317
```

```python
from agentlens import trace, span

@trace                          # records an agent_step span for the whole call
def research_agent(question: str) -> str:
    with span("search", type="tool_call", input=question):
        ...
    return answer
```

## License

[MIT](LICENSE) © 2026 Piyush Singh Tomar
