#!/bin/sh
# Spike E8.5 (throwaway): the executable of "claudia composes.app" (Contents/MacOS/claudia-composes).
# Prepares the window's folder, then `exec`s window.sh, which `exec`s the Neutralino binary inside this same app: the
# process macOS launched becomes the window. CLAUDIA_SPIKE_RUNTIME exists for the spike's own test.
app=composes
R="${CLAUDIA_SPIKE_RUNTIME:-/Library/Application Support/Claudia/runtime}"
B="$(cd "$(dirname "$0")" && pwd)"
L="$HOME/Library/Logs/Claudia"
mkdir -p "$L"
echo "--- $(date '+%Y-%m-%d %H:%M:%S') start, pid $$" >>"$L/$app.log"
"$R/node/bin/node" "$R/spike/prepare.mjs" "$app" "$R" "$B/neutralino" >>"$L/$app.log" 2>&1 || exit 1
exec /bin/sh "$HOME/Library/Caches/Claudia/run/$app/window.sh" >>"$L/$app.log" 2>&1
