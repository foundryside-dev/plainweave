from __future__ import annotations

import argparse
from collections.abc import Callable, Sequence
from typing import cast

from charter import __version__
from charter.cli_commands import register_commands

DESCRIPTION = "Charter requirements and verification authority."
EPILOG = "Local-core commands are available for init and diagnostics."


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="charter", description=DESCRIPTION, epilog=EPILOG)
    parser.add_argument("--version", action="store_true", help="Print the Charter version and exit.")
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
        print(f"charter {__version__}")
        return 0
    handler = getattr(args, "handler", None)
    if handler is not None:
        return cast(Callable[[argparse.Namespace], int], handler)(args)
    parser.print_help()
    return 0
