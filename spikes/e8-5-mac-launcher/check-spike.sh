#!/bin/sh
# Spike E8.5 (throwaway): collects what the spike is meant to find out. Run it twice and paste both outputs:
#   sh spikes/e8-5-mac-launcher/check-spike.sh open     while claudia composes (the spike) is open
#   sh spikes/e8-5-mac-launcher/check-spike.sh quit     about half a minute after quitting it (Cmd+Q)
# It prints no environment values: only those named CLAUDIA_*.
moment="${1:-open}"
app="/Applications/claudia composes.app"
run="$HOME/Library/Caches/Claudia/run/composes"
section() { printf '\n== %s\n' "$1"; }

section "moment: $moment; $(sw_vers -productName) $(sw_vers -productVersion), $(uname -m)"
section "installed files (quarantine? none expected)"
ls -ld "$app" "/Library/Application Support/Claudia/runtime" 2>&1
xattr -l "$app" "$app/Contents/MacOS/claudia-composes" "$app/Contents/MacOS/neutralino" 2>&1 | grep -i quarantine || echo "no quarantine attribute"
section "signatures"
codesign -dv "$app/Contents/MacOS/neutralino" 2>&1 | grep -E "^(Identifier|Signature|CodeDirectory)"
codesign --verify --verbose=1 "$app" 2>&1
section "apps macOS knows as running (one 'claudia composes' expected while open, none after quitting)"
lsappinfo list 2>/dev/null | grep -i -A3 'claudia' || echo "none"
section "processes"
ps -axo pid,ppid,comm | grep -iE "claudia|neutralino|/node( |$)|claudia_server" | grep -v grep || echo "none"
section "window.sh (only its exec line and the CLAUDIA_* lines)"
grep -E "^exec |^export CLAUDIA_" "$run/window.sh" 2>&1
section "the app's log (last 30 lines)"
tail -n 30 "$HOME/Library/Logs/Claudia/composes.log" 2>&1
section "Neutralino's log (last 15 lines)"
tail -n 15 "$run/neutralinojs.log" 2>&1
section "the core's log (last 15 lines)"
tail -n 15 "$HOME/Library/Application Support/Claudia/composes/state/shell.log" 2>&1
