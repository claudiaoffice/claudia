---
id: D360
title: "One key table for every app and every client; the page listens"
status: current
applies-to: all
date: 2026-11-13
round: "QA follow-up: UX consistency across clients (UX-35, UX-36)"
supersedes: []
superseded-by: []
---

# D360 · One key table for every app and every client; the page listens

**Every menu entry has a key, and it is the same key in composes, computes and creates, in the browser and in the
Linux, Windows and macOS shells.** The table is the shared menu manifest (`clients/linux/src/claudia_shell_gtk/
manifest.py`); `scripts/generate_keys.py` writes the web app's copy (`web/app/lib/keys.generated.ts`), and a test fails
when the two differ. The only entries without a key are the language picker's (each a language's own name).

**The page listens for the keys, in every client.** Each key has an owner: the *page* (almost all: the web app's
`menuShortcuts` runs the menu entry as if clicked, with its usual rules, for example no shortcut while typing in a
field), the *shell* (Quit, About, and Shift+F10, which a web view would otherwise keep for its context menu), or the
*view* (Enter, Delete, Tab and the clipboard, handled by the document view or the browser where pressed; the menus only
show them). GTK binds only the shell's keys and shows the others with the GMenu `accel` attribute; the Windows menu
shows them all; the macOS menu claims the Cmd+letter ones.

**How the keys were chosen.** Platform keys where there are any (Ctrl+O, S, P, Z, Shift+Z, C, X, V, F, Ctrl+Shift+S,
Ctrl+Shift+V; F1 Help, Ctrl+? Shortcuts as in GNOME; Ctrl+M New Slide as in PowerPoint and Google Slides; Shift+F11 New
Sheet and Ctrl+F3 Names as in Excel). Never a key a browser keeps for itself, because the web app is a client too: Ctrl+N,
Ctrl+W and Ctrl+T (with or without Shift) never reach a page, so New is Ctrl+Alt+N and Close Document Ctrl+Alt+W. An
app's own commands are Ctrl+Alt+letter, never with Q, E, M or a digit (on Windows Ctrl+Alt is AltGr, which types @, €, µ
and the brackets on a German keyboard), nor T or L (Ubuntu's terminal and lock). The rare, weighty entries of File ▸
Manage ▸ are Ctrl+Alt+Shift+letter. A key matches by the character it types, and by its place only when it typed no
letter or digit (Shift+8, Option+R): places differ between layouts.

**Notes.** Owner's request of 2026-11-13: "make shortcuts consistent across all three apps", after QA found 30–37
entries per app without a key and keys that worked in one client and not another (Ctrl+N was bound by the Linux shell,
listened for by nobody on Windows and kept by every browser). Supersedes the part of D122 that left each workspace its
own hand-written chords; D122's per-OS sets are still the way to a Mac variant: Cmd+M (New Slide) is macOS's Minimize,
and Cmd+Option+H (History and Chat) its Hide Others. The full table is in `notes/keyboard-shortcuts.md`. Proposed by
Claude; the table is data in one place, so changing a key is one line and a regeneration.
