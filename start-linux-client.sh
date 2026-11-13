#!/bin/sh
#   ./start-client.sh [composes|computes|creates] [--server URL] [--debug]      (the app defaults to composes)
#
# Starts the Linux desktop client (clients/linux, the GTK shell) directly — distinct from ./start.sh, which starts a
# server and opens it in a browser instead. See clients/linux/README.md's "Two interpreters" for the full story; in
# short, unlike start.sh, this script cannot just hand everything to `uv run`:
#
#   * the shell itself needs GTK, libadwaita and WebKitGTK from the distribution, and only the system Python
#     (/usr/bin/python3) can import those bindings — a uv-managed interpreter cannot (compatibility note 1 there);
#   * the server it starts needs Python 3.14 and the Claudia packages, which only `.venv` (made by `uv sync`) has.
#
# So this script keeps `.venv` and the built web frontend ready — what the README's "Running it from a checkout"
# otherwise has a person do by hand — and then hands off to the system Python, which is what actually opens the
# window and, in turn, starts the server on the other interpreter (clients/linux/src/claudia_shell_gtk/server.py).
set -e
cd "$(dirname "$0")" || exit 1

uv sync --quiet

# Rebuilds every run, matching the README's manual steps exactly: the Linux client only ever loads the *bundled*
# frontend (D43), never a dev server, so a "build once, skip if present" guard here silently went on serving
# whatever was built the very first time this script ran — several rounds of web/ fixes behind, by the time of the
# owner's 2026-11-06 report that a dialog in the Linux client still looked like an old build while the same dialog
# in the browser (served fresh) looked right. Skip only on request, once a person knows their build is current.
if [ "${CLAUDIA_SKIP_WEB_BUILD:-}" != "1" ]; then
    echo "Building the web app…"
    (cd web && npm ci && npm run build)
fi

if [ ! -x /usr/bin/python3 ]; then
    echo "Claudia's Linux client needs the system Python at /usr/bin/python3, and none was found there." >&2
    echo "See clients/linux/README.md for what the client needs and how to install it." >&2
    exit 1
fi

# The first argument names the app unless it is an option: ./start-client.sh --debug starts composes, as it always did.
case "${1:-}" in
    composes|computes|creates) app="$1"; shift ;;
    *) app=composes ;;
esac

PYTHONPATH="$PWD/clients/linux/src" exec /usr/bin/python3 -m claudia_shell_gtk "$app" "$@"
