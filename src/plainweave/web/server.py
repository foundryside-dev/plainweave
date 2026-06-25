from __future__ import annotations

import argparse
from pathlib import Path

WEB_EXTRA_HINT = (
    "The web UI needs the optional 'web' extra. Install it with:\n"
    "    pip install plainweave[web]\n"
    "(or: uv pip install 'plainweave[web]')"
)


def add_web_subcommand(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    parser = subparsers.add_parser("web", help="Run the operator-facing web UI (needs plainweave[web]).")
    parser.add_argument("--host", default="127.0.0.1", help="Bind host (default: 127.0.0.1).")
    parser.add_argument("--port", type=int, default=8765, help="Bind port (default: 8765).")
    parser.add_argument("--actor", default=None, help="Operator actor id (default: from config / first-run).")
    parser.add_argument(
        "--no-open",
        dest="open_browser",
        action="store_false",
        help="Do not open a browser on start.",
    )
    parser.set_defaults(open_browser=True, handler=_handle)


def _handle(args: argparse.Namespace) -> int:
    return run_web(host=args.host, port=args.port, actor=args.actor, open_browser=args.open_browser)


def run_web(*, host: str, port: int, actor: str | None, open_browser: bool, root: Path | None = None) -> int:
    try:
        return _serve(host=host, port=port, actor=actor, open_browser=open_browser, root=root)
    except ModuleNotFoundError:
        print(WEB_EXTRA_HINT)
        return 1


def _serve(  # pragma: no cover
    *, host: str, port: int, actor: str | None, open_browser: bool, root: Path | None = None
) -> int:
    # Lazy import: only touches starlette/uvicorn when the extra is installed.
    import uvicorn  # noqa: PLC0415, I001

    from plainweave.web.app import create_app  # noqa: PLC0415, I001

    app = create_app(actor=actor, root=root)
    if open_browser:
        _open_browser_later(host, port)
    uvicorn.run(app, host=host, port=port, log_level="info")
    return 0


def _open_browser_later(host: str, port: int) -> None:  # pragma: no cover
    import threading
    import webbrowser

    url = f"http://{host}:{port}/"
    threading.Timer(0.8, lambda: webbrowser.open(url)).start()
