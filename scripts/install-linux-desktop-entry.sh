#!/bin/sh
#   scripts/install-linux-desktop-entry.sh composes|computes|creates
#
# Lets GNOME (and other desktops) show the app's own icon for a Linux client started from this checkout. On Wayland a
# window has no icon of its own: the dock looks for the desktop entry named after the window's app id
# (de.claudiaoffice.<app>.desktop) and takes the icon from there. An installed package puts that entry in
# /usr/share/applications; a checkout has it only in clients/linux/apps/<app>/, where nothing looks. So this copies the
# entry and the icon into the person's own folders ($XDG_DATA_HOME, ~/.local/share by default), with Exec pointing at
# this checkout's start-linux-client.sh. It is run by start-linux-client.sh every time (cheap, and a moved checkout
# fixes itself) and touches nothing else.
set -e
app="${1:?usage: install-linux-desktop-entry.sh composes|computes|creates}"
case "$app" in
    composes|computes|creates) ;;
    *) echo "unknown app: $app" >&2; exit 2 ;;
esac
repo="$(cd "$(dirname "$0")/.." && pwd)"
id="de.claudiaoffice.$app"
source_dir="$repo/clients/linux/apps/$app"
data="${XDG_DATA_HOME:-}"
case "$data" in /*) ;; *) data="$HOME/.local/share" ;; esac

mkdir -p "$data/applications" "$data/icons/hicolor/scalable/apps"
cp "$source_dir/icons/hicolor/scalable/apps/$id.svg" "$data/icons/hicolor/scalable/apps/$id.svg"
# Exec and TryExec point at this checkout; everything else is the entry an installed package has.
sed -e "s|^Exec=.*|Exec=\"$repo/start-linux-client.sh\" $app|" \
    -e "/^TryExec=/d" \
    "$source_dir/$id.desktop" > "$data/applications/$id.desktop.tmp"
mv "$data/applications/$id.desktop.tmp" "$data/applications/$id.desktop"
if command -v update-desktop-database >/dev/null 2>&1; then
    update-desktop-database -q "$data/applications" 2>/dev/null || true
fi
