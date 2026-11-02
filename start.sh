#!/bin/sh
# Start the Claudia demo (Linux, macOS). Options: see `./start.sh --help`.
cd "$(dirname "$0")" || exit 1
exec uv run python scripts/start.py "$@"
