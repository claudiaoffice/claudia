---
id: D158
title: "Proposal: the shell contract and the manifest carry what the OSes differ on"
status: current
applies-to: all
date: 2026-11-07
round: "Neutralino on Windows and macOS (twenty-eighth round)"
supersedes: []
superseded-by: []
---

# D158 · Proposal: the shell contract and the manifest carry what the OSes differ on

**Proposal: the shell contract and the manifest carry what the OSes differ on.** (1) Each Edit item names a **role** (undo, redo, cut, copy, paste, select all) next to its accelerator in a platform-neutral form; the shell maps it: the Cocoa selector (`copy:` …) and `shortcut` on macOS, `execute_editing_command` on Linux, `execCommand` in the page on Windows. Without it Cmd+C does nothing on macOS. (2) **Printing is a shell service**: a print request in the contract, because the macOS web view has no `window.print()` (Neutralino: `window.print()` from the native API); the page falls back to the browser's. (3) **About stays a page dialog** where the shell reports `nativeAbout: false` (Windows, macOS), as `AboutDialog.vue` already works.

**Notes.** Refines D44 (its note already named the macOS Edit problem) and D74 (Cut, Copy, Paste in Edit). The Linux manifest has GTK-syntax accelerators but no role field; the v1 contract has no print message. Both are additive changes (E5.1, E5.12). Select All is still undecided for every menu. **Built, 2026-11-07 (E5.11):** (1) is done — `manifest.py` gained an `Action.role` field, set on the shared Undo/Redo/Copy/Cut/Paste block and carried through `describe()`; `macos-client:clients/macos/src/menu.ts` maps each role to its Cocoa selector plus a `ROLE_SHORTCUT` accelerator (no `redo:` shortcut yet — no confirmed Neutralino grammar for Cmd+Shift+Z was found). (3) is done — `help.about` is forwarded to the page despite being `Kind.SHELL` in the manifest. (2) is still not done: `Neutralino.window.print()` is typed in the macOS client's `NeutralinoLike` interface but the contract has no print message yet and nothing calls it. Select All remains undecided. **Built, 2026-11-08 (E5.11, Windows):** (1) does not apply the same way — Windows has no Cocoa selector to route a `role` through at all, so `clients/windows/src/menu.ts` reads nothing from the field (it stays in the shared manifest for macOS's sake and is carried through `generate_menu.py`'s JSON unused); every Edit item, standard ones included, is forwarded to the page as a plain `action` message, the same path Linux already uses for Undo/Redo. (3) is done, same as macOS — `help.about` forwards to the page. (2) is still not done, same as macOS.

*Written as a proposal; confirmed by the owner on 2026-11-10, since the code already follows it.*
