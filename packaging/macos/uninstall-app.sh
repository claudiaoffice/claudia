#!/bin/sh
# The program of "uninstall claudia.app" (E8.5, D1628): says what will happen, asks macOS for an administrator's
# password, runs the runtime's uninstall.sh as root, and says that claudia is removed, or what failed. In English or
# German, as the Mac's first language is (D1625). A script app, not an AppleScript applet: the package is built on
# Linux, which has no osacompile (the owner, 2026-11-26).
S="/Library/Application Support/Claudia/runtime/uninstall.sh"

case "$(defaults read -g AppleLanguages 2>/dev/null | sed -n 2p | tr -d ' ",')" in
  de*)
    CONFIRM="Hiermit wird claudia von diesem Mac entfernt. Geöffnete Apps von claudia, auch die anderer Personen dieses Macs, werden geschlossen. Dokumente und Einstellungen bleiben."
    CANCEL="Abbrechen"
    REMOVE="Entfernen"
    DONE="claudia ist entfernt. Diese Ordner bleiben: die geteilten Dokumente in /Library/Application Support/Claudia/shared/documents und die eigenen Dokumente und Einstellungen jeder Person in ~/Library/Application Support/Claudia. Löschen Sie sie, wenn Sie sie nicht mehr brauchen."
    FAILED="claudia konnte nicht entfernt werden:"
    ABSENT="claudia ist auf diesem Mac nicht installiert."
    ;;
  *)
    CONFIRM="This removes claudia from this Mac. claudia's apps that are open, also those of other people of this Mac, are closed. Documents and settings stay."
    CANCEL="Cancel"
    REMOVE="Uninstall"
    DONE="claudia is removed. These folders are left: the shared documents in /Library/Application Support/Claudia/shared/documents, and each person's own documents and settings in ~/Library/Application Support/Claudia. Delete them if you no longer need them."
    FAILED="claudia could not be removed:"
    ABSENT="claudia is not installed on this Mac."
    ;;
esac

say() {
  osascript -e 'on run argv' -e 'display dialog (item 1 of argv) buttons {"OK"} default button "OK" with title "uninstall claudia"' \
    -e 'end run' "$1" >/dev/null
}

if [ ! -x "$S" ]; then
  say "$ABSENT"
  exit 0
fi
osascript -e 'on run argv' \
  -e 'display dialog (item 1 of argv) buttons {item 2 of argv, item 3 of argv} default button 2 cancel button 2 with title "uninstall claudia" with icon caution' \
  -e 'end run' "$CONFIRM" "$CANCEL" "$REMOVE" >/dev/null 2>&1 || exit 0

if words="$(osascript -e 'on run argv' -e 'do shell script (quoted form of (item 1 of argv)) with administrator privileges' -e 'end run' "$S" 2>&1)"; then
  say "$DONE"
else
  case "$words" in
    *"-128"*) exit 0 ;; # she cancelled the password dialog
  esac
  say "$FAILED $words"
  exit 1
fi
