#!/bin/sh
# Starts the macOS desktop client (clients/macos, the Neutralino shell) directly -- the macOS counterpart of
# ./start-client.sh (Linux/GTK). Unlike that script, there is no second system interpreter to hand off to here:
# the macOS client itself is plain Node/TypeScript, not Python at all, so there is nothing like GTK's
# distribution-Python split (D116) to work around on this side. What's left is still enough manual setup that
# clients/macos/README.md's "Running it from a checkout" spells it out step by step -- this script does that setup
# and then runs the built launcher itself:
#
#   * `.venv` (via `uv sync`) is what the *server* runs on -- same Python 3.14 requirement as Linux, same reason
#     (D116): the server is outside the uv workspace's own Node/TS half.
#   * The web frontend is rebuilt every run, not just built once and left stale -- see start-client.sh's own
#     comment on the 2026-11-06 report that caught exactly that bug for the Linux client. Skip with
#     CLAUDIA_SKIP_WEB_BUILD=1 once you know your build is current.
#   * The macOS client's own TypeScript (tsc, then the injected-script bundle) is rebuilt every run for the same
#     reason. Skip with CLAUDIA_SKIP_MACOS_BUILD=1.
#   * The Neutralino binary (not checked into the repo, D157) is fetched automatically with
#     `npx @neutralinojs/neu update` the first time it is missing -- the step clients/macos/README.md otherwise
#     has you run by hand in apps/<app>/.
#
# Usage: ./start-mac-client.sh [app]   -- app defaults to "creates", the only one built so far (E5.11).
set -e
cd "$(dirname "$0")" || exit 1

APP="${1:-creates}"
APP_DIR="clients/macos/apps/$APP"

if ! command -v node >/dev/null 2>&1; then
    echo "Claudia's macOS client needs Node.js, and none was found on PATH." >&2
    echo "Install it from https://nodejs.org and run this again." >&2
    exit 1
fi

uv sync --quiet

if [ "${CLAUDIA_SKIP_WEB_BUILD:-}" != "1" ]; then
    echo "Building the web app..."
    (cd web && npm ci && npm run build)
fi

if [ "${CLAUDIA_SKIP_MACOS_BUILD:-}" != "1" ]; then
    echo "Building the macOS client..."
    (cd clients/macos && npm ci && npm run build)
fi

if [ ! -d "$APP_DIR" ]; then
    echo "'$APP' has no macOS client yet -- this first version only covers creates (E5.11)." >&2
    exit 1
fi

if [ -z "${CLAUDIA_NEUTRALINO_BIN:-}" ] && ! ls "$APP_DIR"/bin/neutralino-mac_* >/dev/null 2>&1; then
    echo "Fetching the Neutralino binary for $APP (npx @neutralinojs/neu update)..."
    (cd "$APP_DIR" && npx --yes @neutralinojs/neu update)
fi

exec node clients/macos/dist/launch.js "$APP"
