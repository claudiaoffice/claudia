#!/bin/sh
# The program of "uninstall claudia.app" (E8.5, D1628): says what will happen, asks macOS for an administrator's
# password, runs the runtime's uninstall.sh as root, and shows its last words. A script app, not an AppleScript applet:
# the package is built on Linux, which has no osacompile (the owner, 2026-11-26).
S="/Library/Application Support/Claudia/runtime/uninstall.sh"

say() {
  /usr/bin/osascript -e 'on run argv' -e 'display dialog (item 1 of argv) buttons {"OK"} default button "OK" with title "uninstall claudia"' -e 'end run' "$1" >/dev/null
}

if [ ! -x "$S" ]; then
  say "claudia is not installed on this Mac."
  exit 0
fi
/usr/bin/osascript -e 'on run argv' \
  -e 'display dialog (item 1 of argv) buttons {"Cancel", "Uninstall"} default button "Cancel" cancel button "Cancel" with title "uninstall claudia" with icon caution' \
  -e 'end run' \
  "This removes claudia from this Mac. claudia's apps that are open, also those of other people of this Mac, are closed. Documents and settings stay." \
  >/dev/null 2>&1 || exit 0

if words="$(/usr/bin/osascript -e 'on run argv' -e 'do shell script (quoted form of (item 1 of argv)) with administrator privileges' -e 'end run' "$S" 2>&1)"; then
  say "$words"
else
  case "$words" in
    *"-128"*) exit 0 ;; # she cancelled the password dialog
  esac
  say "claudia could not be removed: $words"
  exit 1
fi
