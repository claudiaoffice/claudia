"""``python -m claudia_fonts fetch DIR``: fetch the starter set of fonts into DIR (see :mod:`claudia_fonts.starter`)."""

from __future__ import annotations

import argparse
import sys

from .starter import FetchError, fetch


def main(argv: list[str] | None = None) -> int:
    """Run the command line; the exit status."""
    parser = argparse.ArgumentParser(
        prog="python -m claudia_fonts", description="The font collection of a Claudia server."
    )
    commands = parser.add_subparsers(dest="command", required=True)
    get = commands.add_parser("fetch", help="fetch the starter set of open fonts into a folder (pinned by SHA-256)")
    get.add_argument("folder", help="where the collections go, one subfolder each; give it to the server with --fonts")
    args = parser.parse_args(argv)
    try:
        folders = fetch(args.folder, report=lambda line: print(line, flush=True))
    except FetchError as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    print(f"{len(folders)} collections in {args.folder}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
