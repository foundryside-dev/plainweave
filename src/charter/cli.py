from __future__ import annotations

import argparse
from collections.abc import Sequence

from charter import __version__

DESCRIPTION = "Charter requirements and verification authority."
EPILOG = "No domain commands are implemented in this scaffold yet."


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="charter", description=DESCRIPTION, epilog=EPILOG)
    parser.add_argument("--version", action="store_true", help="Print the Charter version and exit.")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    if argv is not None and any(arg in {"-h", "--help"} for arg in argv):
        parser.print_help()
        return 0
    args = parser.parse_args(argv)
    if args.version:
        print(f"charter {__version__}")
        return 0
    parser.print_help()
    return 0
