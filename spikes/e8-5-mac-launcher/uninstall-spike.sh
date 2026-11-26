#!/bin/sh
# Spike E8.5 (throwaway): removes what claudia-composes-spike.pkg installed. Asks for an administrator's password.
#   sh spikes/e8-5-mac-launcher/uninstall-spike.sh
# Leaves ~/Library/Application Support/Claudia (documents, settings): the checkout's own start-mac-client.sh uses it too.
set -u
pkill -f "/Applications/claudia composes.app/Contents/MacOS/" 2>/dev/null
pkill -f "/Library/Application Support/Claudia/runtime/" 2>/dev/null
sudo rm -rf "/Applications/claudia composes.app" "/Library/Application Support/Claudia/runtime"
sudo rmdir "/Library/Application Support/Claudia" 2>/dev/null
sudo pkgutil --forget de.claudiaoffice.spike.launcher >/dev/null 2>&1
rm -rf "$HOME/Library/Caches/Claudia/run/composes"
echo "removed the spike's app and runtime"
