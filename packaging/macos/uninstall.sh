#!/bin/sh
# Removes claudia from this Mac (E8.5, D1628), as root: "uninstall claudia.app" runs it with an administrator's
# password. It leaves only documents and settings: the shared documents, and each person's own folder with her
# documents, settings and logs. $1 is the volume (the start volume when not given).
T="${1%/}"
C="$T/Library/Application Support/Claudia"
LABEL="de.claudia-office.server"
ACCOUNT="_claudia"

# The service, and every process of claudia: the apps' windows and servers of every person of this Mac.
if launchctl print "system/$LABEL" >/dev/null 2>&1; then
  launchctl bootout "system/$LABEL" || true
fi
rm -f "$T/Library/LaunchDaemons/$LABEL.plist" "$C/service.json"
# Matched by what they run, not by the runtime's folder: this script and the shell that started it are in it too.
pkill -f "$C/runtime/(node|server|python)/" || true
pkill -f "/Library/Caches/Claudia/run/" || true
pkill -f "$T/Applications/claudia (composes|computes|creates)\.app/Contents/MacOS/" || true

# The shared folders stay, owned by the administrators; the account goes.
if [ -d "$C/shared" ]; then
  chown -R root:admin "$C/shared"
fi
if dscl . -read "/Users/$ACCOUNT" >/dev/null 2>&1; then
  dscl . -delete "/Users/$ACCOUNT"
fi
if dscl . -read "/Groups/$ACCOUNT" >/dev/null 2>&1; then
  dscl . -delete "/Groups/$ACCOUNT"
fi

# The apps, this uninstaller, the runtime, the service's log, and each person's copies of the apps (Caches).
for app in composes computes creates; do
  rm -rf "$T/Applications/claudia $app.app"
done
rm -rf "$T/Applications/Utilities/uninstall claudia.app" "$C/runtime" "$T/Library/Logs/Claudia"
for home in "$T"/Users/*; do
  rm -rf "$home/Library/Caches/Claudia"
done
for receipt in de.claudia-office.apps de.claudia-office.service; do
  pkgutil --volume "${T:-/}" --forget "$receipt" >/dev/null 2>&1 || true
done

echo "claudia is removed. These folders are left: the shared documents in /Library/Application Support/Claudia/shared/documents, and each person's own documents and settings in ~/Library/Application Support/Claudia. Delete them if you no longer need them."
