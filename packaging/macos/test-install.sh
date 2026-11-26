#!/bin/sh
# The install test of the macOS package (E8.5, D1629): what CI cannot do, since it has no Mac. Run it on a Mac with
# Apple Silicon and macOS 14 or newer (or in a macOS virtual machine), from a checkout, as an administrator:
#
#     sudo packaging/macos/test-install.sh ~/Downloads/claudia-office-0.5.0-macos-arm64.pkg
#
# It installs the package without the service, then with it, then over itself, and uninstalls it, and checks after each
# step what specs/desktop/macos-installer.feature asks. It removes claudia at the end; documents of an earlier
# installation stay, as the uninstaller leaves them. It opens windows of claudia composes in the session of the person
# who runs it (sudo from her account, logged in at the Mac's screen). What needs a person's eyes -- "Open Anyway" for a
# downloaded package, one Dock icon with the app's name -- is not checked here: look once while it runs.
set -u
PKG="${1:?usage: sudo $0 claudia-office-<version>-macos-arm64.pkg}"
HERE="$(cd "$(dirname "$0")" && pwd)"
C="/Library/Application Support/Claudia"
R="$C/runtime"
LABEL="de.claudia-office.server"
PERSON="${SUDO_USER:-}"
FAILED=0
CHECKED=0

check() { # check "what" command...
  what="$1"
  shift
  CHECKED=$((CHECKED + 1))
  if "$@" >/dev/null 2>&1; then
    echo "ok    $what"
  else
    echo "FAIL  $what"
    FAILED=$((FAILED + 1))
  fi
}
absent() { [ ! -e "$1" ]; }
running() { launchctl print "system/$LABEL" >/dev/null 2>&1; }
answers() { # answers PORT: the server says it is healthy within a minute
  i=0
  while [ "$i" -lt 60 ]; do
    curl -fsS "http://127.0.0.1:$1/api/health" >/dev/null 2>&1 && return 0
    sleep 1 # work: a server that is starting has nothing to wait on but time
    i=$((i + 1))
  done
  return 1
}
as_person() { sudo -u "$PERSON" -H "$@"; }
all_signed() { # codesign checks what macho.py could only see is there: that each signature is valid
  unsigned="$(find "$R" /Applications/claudia\ *.app -type f \( -perm +111 -o -name '*.so' -o -name '*.dylib' \) |
    while IFS= read -r file; do
      if file "$file" | grep -q Mach-O && ! codesign -v "$file" 2>/dev/null; then echo "$file"; fi
    done)"
  [ -z "$unsigned" ] || { echo "$unsigned" >&2; return 1; }
}
GUI_ID=""
as_her() { launchctl asuser "$GUI_ID" sudo -u "$PERSON" -H "$@"; } # in her login session, where windows open
window_of() { pgrep -f "/Applications/claudia $1\.app/Contents/MacOS/neutralino"; }
opens() { # opens APP: its window runs within a minute
  as_her open -a "/Applications/claudia $1.app"
  i=0
  while [ "$i" -lt 60 ]; do
    window_of "$1" >/dev/null && return 0
    sleep 1 # work: macOS starts the app, the launcher prepares, the window comes; nothing to wait on but time
    i=$((i + 1))
  done
  return 1
}
gone_within() { # gone_within SECONDS PATTERN: no process matches within that time
  i=0
  while [ "$i" -lt "$1" ]; do
    pgrep -f "$2" >/dev/null || return 0
    sleep 1 # work: processes end on their own after the window closes
    i=$((i + 1))
  done
  return 1
}
no_claudia_process() {
  ! pgrep -f "$R/(node|server|python)/|/Library/Caches/Claudia/run/|/Applications/claudia (composes|computes|creates)\.app/Contents/MacOS/"
}
install_package() { # install_package [service]
  if [ "${1:-}" = service ]; then
    choices="$(mktemp -t claudia-choices)"
    cat >"$choices" <<'EOF'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><array><dict>
  <key>attributeSetting</key><integer>1</integer>
  <key>choiceAttribute</key><string>selected</string>
  <key>choiceIdentifier</key><string>service</string>
</dict></array></plist>
EOF
    installer -pkg "$PKG" -target / -applyChoiceChangesXML "$choices"
  else
    installer -pkg "$PKG" -target /
  fi
}

if [ "$(uname -s)" != Darwin ] || [ "$(uname -m)" != arm64 ]; then
  echo "Run this on a Mac with Apple Silicon." >&2
  exit 2
fi
[ "$(id -u)" = 0 ] || { echo "Run this with sudo." >&2; exit 2; }
if [ -z "$PERSON" ] || [ "$PERSON" = root ]; then
  echo "Run this with sudo from a person's account." >&2
  exit 2
fi
GUI_ID="$(id -u "$PERSON")"
[ -f "$PKG" ] || { echo "$PKG is not there." >&2; exit 2; }

echo "== The package"
check "it has the installer's parts" sh -c "pkgutil --expand '$PKG' \"\$(mktemp -d)/x\""
[ -x "$R/uninstall.sh" ] && "$R/uninstall.sh" >/dev/null 2>&1

echo "== Installing without changing its parts"
check "the installer succeeds" install_package
for app in composes computes creates; do
  check "claudia $app is in Applications" test -x "/Applications/claudia $app.app/Contents/MacOS/claudia-$app"
done
check "uninstall claudia is in Applications > Utilities" test -d "/Applications/Utilities/uninstall claudia.app"
check "no claudia service runs" sh -c "! launchctl print system/$LABEL"
check "no place is called Shared on this computer (no service file)" absent "$C/service.json"
check "the account _claudia is not there" sh -c "! dscl . -read /Users/_claudia"
check "every program and library is signed and its signature is valid" all_signed
check "an app prepares its window for her" as_person "$R/node/bin/node" "$R/client/dist/launch.js" composes --prepare
check "...in her Caches" test -f "/Users/$PERSON/Library/Caches/Claudia/run/composes/window.sh"
check "the server runs from the runtime" as_person "$R/server/claudia-server" --version
work="$(mktemp -d)"
chmod 777 "$work"
as_person "$R/server/claudia-server" --host 127.0.0.1 --port 8811 --no-tls --dir "$work/documents" \
  --state-dir "$work/state" --web "$R/web" --exit-when-idle 120 >"$work/server.log" 2>&1 &
check "...and answers" answers 8811
check "...as the suite's server does (smoke test)" "$R/python/bin/python3" "$HERE/../smoke_server.py" http://127.0.0.1:8811
pkill -f "port 8811" || true
check "claudia composes opens a window" opens composes
check "...and what its start printed is in her log" test -s "/Users/$PERSON/Library/Logs/Claudia/composes.log"
as_her osascript -e 'quit app id "de.claudia-office.composes"' >/dev/null 2>&1
check "quitting it leaves no process of its window within half a minute" \
  gone_within 30 "/Applications/claudia composes\.app/Contents/MacOS/|/Library/Caches/Claudia/run/composes/"

echo "== Installing with the service"
check "the installer succeeds" install_package service
check "the claudia service runs" running
check "...under its own account" sh -c "ps -axo user,command | grep -v grep | grep '_claudia.*claudia_server'"
check "...and answers on 8765" answers 8765
check "...as the suite's server does (smoke test)" "$R/python/bin/python3" "$HERE/../smoke_server.py" http://127.0.0.1:8765
check "the service file names it" grep -q '127.0.0.1:8765' "$C/service.json"
check "an administrator of this Mac reads its setup code" as_person cat "$C/shared/state/admin/setup-code"
echo "kept" >"$C/shared/documents/test-install-kept.txt"
mkdir -p "/Users/$PERSON/Library/Application Support/Claudia"
echo "kept" >"/Users/$PERSON/Library/Application Support/Claudia/test-install-kept.txt"

echo "== Updating over itself, without changing its parts (the service stays as it is), with an app open"
check "claudia computes opens a window" opens computes
check "the installer succeeds" install_package
check "the open app was closed for the update" gone_within 30 "/Applications/claudia computes\.app/Contents/MacOS/"
check "the shared documents are still there" test -f "$C/shared/documents/test-install-kept.txt"
check "her own folder is still there" test -f "/Users/$PERSON/Library/Application Support/Claudia/test-install-kept.txt"
check "the claudia service runs again" answers 8765

echo "== Uninstalling, with an app open"
check "claudia creates opens a window" opens creates
words="$("$R/uninstall.sh" 2>&1)"
check "the last words say what is left" sh -c "printf '%s' \"\$1\" | grep -q 'claudia is removed. These folders are left'" _ "$words"
for app in composes computes creates; do
  check "claudia $app is gone" absent "/Applications/claudia $app.app"
done
check "uninstall claudia is gone" absent "/Applications/Utilities/uninstall claudia.app"
check "the runtime is gone" absent "$R"
check "the service is gone" sh -c "! launchctl print system/$LABEL"
check "...and its account" sh -c "! dscl . -read /Users/_claudia"
check "no process of claudia runs" no_claudia_process
check "the shared documents are still there" test -f "$C/shared/documents/test-install-kept.txt"
check "her own documents and settings are still there" test -f "/Users/$PERSON/Library/Application Support/Claudia/test-install-kept.txt"
check "her Caches/Claudia is gone" absent "/Users/$PERSON/Library/Caches/Claudia"
check "her logs are still there" test -f "/Users/$PERSON/Library/Logs/Claudia/composes.log"
check "the shared documents are the administrators' to open" as_person cat "$C/shared/documents/test-install-kept.txt"
check "macOS forgot the package" sh -c "! pkgutil --pkg-info de.claudia-office.apps"
rm -f "$C/shared/documents/test-install-kept.txt" "/Users/$PERSON/Library/Application Support/Claudia/test-install-kept.txt"

echo
if [ "$FAILED" -eq 0 ]; then
  echo "PASS: $CHECKED checks"
else
  echo "FAILED: $FAILED of $CHECKED checks"
fi
[ "$FAILED" -eq 0 ]
