#!/bin/sh
# Run the end-to-end tests (Linux, macOS): set this computer up, then run them. Options: see `./run-e2e.sh --help`.
cd "$(dirname "$0")" || exit 1
exec uv run python scripts/run_e2e.py "$@"
