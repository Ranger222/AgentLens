"""``agentlens`` command-line interface.

Subcommands:
  serve   Launch the local dashboard (FastAPI + UI).
  demo    Generate sample traces (no API keys needed).
  info    Show the trace DB path and run count.
  version Print the version.
"""

from __future__ import annotations

import argparse
import sys

from ._version import __version__
from .config import resolve_db_path

DEFAULT_HOST = "127.0.0.1"
# 8765: memorable, unreserved. Deliberately NOT 4317/4318 (OTLP) to avoid
# colliding with otel collectors that this tool's users often run.
DEFAULT_PORT = 8765


def _add_db_arg(p: argparse.ArgumentParser) -> None:
    p.add_argument(
        "--db",
        default=None,
        help="Path to the SQLite trace DB (default: $AGENTLENS_DB or ./agentlens.db).",
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="agentlens",
        description="Chrome DevTools for your AI agents — local-first LLM-agent tracing.",
    )
    parser.add_argument("--version", action="version", version=f"agentlens {__version__}")
    sub = parser.add_subparsers(dest="command")

    p_serve = sub.add_parser("serve", help="Launch the local dashboard.")
    _add_db_arg(p_serve)
    p_serve.add_argument("--host", default=DEFAULT_HOST, help=f"Bind host (default {DEFAULT_HOST}).")
    p_serve.add_argument("--port", type=int, default=DEFAULT_PORT, help=f"Bind port (default {DEFAULT_PORT}).")
    p_serve.add_argument("--reload", action="store_true", help="Auto-reload (dev).")
    p_serve.add_argument("--no-browser", action="store_true", help="Don't open a browser.")

    p_demo = sub.add_parser("demo", help="Generate sample traces (no API keys needed).")
    _add_db_arg(p_demo)
    p_demo.add_argument("-n", "--runs", type=int, default=3, help="How many demo runs to create.")
    p_demo.add_argument("--seed", type=int, default=None, help="Seed RNG for reproducible demos.")

    p_info = sub.add_parser("info", help="Show DB path and run count.")
    _add_db_arg(p_info)

    sub.add_parser("version", help="Print the version.")
    return parser


def _cmd_serve(args: argparse.Namespace) -> int:
    import uvicorn

    from .server.app import create_app, find_webui_dir

    db_path = resolve_db_path(args.db)
    url = f"http://{args.host}:{args.port}"
    has_ui = find_webui_dir() is not None
    print(f"🔍 AgentLens {__version__}")
    print(f"   trace db : {db_path}")
    print(f"   dashboard: {url}{'' if has_ui else '  (UI not built — serving API + placeholder)'}")
    print("   press Ctrl+C to stop")

    if not args.no_browser and not args.reload:
        _open_browser_soon(url)

    if args.reload:
        # reload requires an import string; expose the app via a factory env hook.
        import os

        os.environ["AGENTLENS_DB"] = db_path
        uvicorn.run(
            "agentlens.server.app:create_app",
            factory=True,
            host=args.host,
            port=args.port,
            reload=True,
        )
    else:
        app = create_app(db_path)
        uvicorn.run(app, host=args.host, port=args.port, log_level="info")
    return 0


def _open_browser_soon(url: str) -> None:
    import threading
    import webbrowser

    def _open() -> None:
        import time

        time.sleep(1.0)
        try:
            webbrowser.open(url)
        except Exception:  # noqa: BLE001
            pass

    threading.Thread(target=_open, daemon=True).start()


def _cmd_demo(args: argparse.Namespace) -> int:
    from .demo import run_demo

    db_path = run_demo(db_path=args.db, runs=args.runs, seed=args.seed)
    print(f"✅ Generated {args.runs} demo run(s) in {db_path}")
    print("   View them with:  agentlens serve")
    return 0


def _cmd_info(args: argparse.Namespace) -> int:
    import os

    from .storage.sqlite import SQLiteStorage

    db_path = resolve_db_path(args.db)
    print(f"agentlens {__version__}")
    print(f"db path : {db_path}")
    if not os.path.exists(db_path):
        print("db status: not created yet (run an agent or `agentlens demo`)")
        return 0
    store = SQLiteStorage(db_path)
    try:
        runs = store.count_runs()
        print(f"db status: ok ({runs} run{'s' if runs != 1 else ''})")
    finally:
        store.close()
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command in (None,):
        parser.print_help()
        return 0
    if args.command == "version":
        print(f"agentlens {__version__}")
        return 0
    if args.command == "serve":
        return _cmd_serve(args)
    if args.command == "demo":
        return _cmd_demo(args)
    if args.command == "info":
        return _cmd_info(args)
    parser.print_help()
    return 1


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
