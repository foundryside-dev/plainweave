from __future__ import annotations

import argparse
from collections.abc import Callable, Sequence
from typing import cast

from plainweave import __version__
from plainweave.cli_commands import register_commands

DESCRIPTION = "Plainweave requirements and verification authority."
EPILOG = "Local-core commands are available for requirements, criteria, trace, init, and diagnostics."


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="plainweave", description=DESCRIPTION, epilog=EPILOG)
    parser.add_argument("--version", action="store_true", help="Print the Plainweave version and exit.")
    subparsers = parser.add_subparsers(dest="command")
    register_commands(subparsers)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    if argv is not None and list(argv) in (["-h"], ["--help"]):
        parser.print_help()
        return 0
    args = parser.parse_args(argv)
    if args.version:
        print(f"plainweave {__version__}")
        return 0
    handler = getattr(args, "handler", None)
    if handler is not None:
        return cast(Callable[[argparse.Namespace], int], handler)(args)
    parser.print_help()
    return 0
