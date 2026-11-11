#!/bin/sh
#   ./start-mac-client.sh [composes|computes|creates] [--server URL] [--debug]      (the app defaults to composes)
#
# Starts the macOS desktop client (clients/macos, the Neutralino shell) directly -- the macOS counterpart of
# ./start-client.sh (Linux/GTK), with the same arguments. Unlike that script, there is no second system interpreter to
# hand off to: the macOS client itself is Node/TypeScript, not Python at all. What is left is setup that
# clients/macos/README.md's "Running it from a checkout" otherwise has a person do by hand:
#
#   * `.venv` (via `uv sync --no-dev`) is what the *server* runs on -- same Python 3.14 requirement as Linux, same reason
#     (D116). `--no-dev`: the client needs none of the documentation tools of the dev group, one of which can force a
#     source build that needs a C toolchain on a very recent Python (found for the Windows client, see its CHANGELOG).
#   * The web frontend is rebuilt every run, not just built once and left stale -- see start-client.sh's own
#     comment on the 2026-11-06 report that caught exactly that bug for the Linux client. Skip with
#     CLAUDIA_SKIP_WEB_BUILD=1 once you know your build is current.
#   * The macOS client's own TypeScript and the three app pages are rebuilt every run for the same reason. Skip with
#     CLAUDIA_SKIP_MACOS_BUILD=1.
#   * The Neutralino binary and client library (not checked into the repo, D157) are fetched automatically with
#     `npx @neutralinojs/neu update` the first time they are missing.
#
# `--server URL` connects to a server (https; plain http only for this computer) instead of starting one here. The
# checkout must be in a folder without spaces in its path.
set -e
cd "$(dirname "$0")" || exit 1

# The first argument names the app unless it is an option: ./start-mac-client.sh --debug starts composes.
case "${1:-}" in
    composes|computes|creates) app="$1"; shift ;;
    *) app=composes ;;
esac
APP_DIR="clients/macos/apps/$app"

if ! command -v node >/dev/null 2>&1; then
    echo "Claudia's macOS client needs Node.js (version 22 or newer), and none was found on PATH." >&2
    echo "Install it from https://nodejs.org and run this again." >&2
    exit 1
fi

uv sync --quiet --no-dev

if [ "${CLAUDIA_SKIP_WEB_BUILD:-}" != "1" ]; then
    echo "Building the web app..."
    (cd web && npm ci && npm run build)
fi

if [ "${CLAUDIA_SKIP_MACOS_BUILD:-}" != "1" ]; then
    echo "Building the macOS client..."
    (cd clients/macos && npm ci && npm run build)
fi

if [ -z "${CLAUDIA_NEUTRALINO_BIN:-}" ] && { ! ls "$APP_DIR"/bin/neutralino-mac_* >/dev/null 2>&1 || [ ! -f "$APP_DIR/js/neutralino.js" ]; }; then
    echo "Fetching Neutralino for $app (npx @neutralinojs/neu update)..."
    (cd "$APP_DIR" && npx --yes @neutralinojs/neu update)
fi

exec node clients/macos/dist/launch.js "$app" "$@"
