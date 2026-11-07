#!/bin/sh
# Starts the Neutralino shell with the shared test page (E0.3).
# Needs Node.js (only to download Neutralino's ~2 MB binaries with the "neu" tool).
# Optional: "uv" (https://docs.astral.sh/uv/) or python3, for the local-server checks.
# First run:  chmod +x run_macos.sh   (or: sh run_macos.sh)
# "sh run_macos.sh direct" starts the binary without the "neu run" harness (used to test the token problem).
set -e
cd "$(dirname "$0")"

if ! command -v node >/dev/null 2>&1; then
  echo "Node.js was not found. Install it from https://nodejs.org and run this again." >&2
  exit 1
fi

node ../fetch-vendor.mjs

echo "Copying the shared page and the test server ..."
mkdir -p resources server
cp -R ../page/. resources/
cp -R ../server/. server/

if [ ! -d bin ]; then
  echo "Downloading Neutralino binaries ..."
  npx --yes @neutralinojs/neu@11.8.0 update
fi

if [ "${1:-}" = "direct" ]; then
  # Starts the binary itself, without the "neu run" development harness (no auth export, no auto-reload, no CLI connection).
  case "$(uname -m)" in arm64) BIN=bin/neutralino-mac_arm64 ;; *) BIN=bin/neutralino-mac_x64 ;; esac
  echo "Starting $BIN directly ..."
  chmod +x "$BIN"
  exec "$BIN" --load-dir-res --path=.
fi

echo "Starting ..."
npx --yes @neutralinojs/neu@11.8.0 run
