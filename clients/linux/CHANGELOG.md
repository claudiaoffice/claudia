# Changelog of the Linux client and the shell contract

Newest first. The shell contract has its own version (`clients/contract/`); this file lists both.

## [0.1.0] - unreleased

First slice of the native Linux client (epic 5), for composes only.

### Added
- `claudia-composes`: GTK 4 / libadwaita window with the native menus File, Edit, Tools and Help (D4), a History and
  Chat toggle in the header bar (D40) and an About dialog (D28); application id `de.claudiaoffice.composes`.
- A local server per window (loopback, plain, the bundled frontend served from the same origin) that is ended with the
  window and when the shell dies.
- Shell contract **version 1** (`clients/contract/shell-contract.v1.schema.json`): `hello`, `welcome`, `action`,
  `action_state`, `error`.
- A page adapter that lets the unchanged web app take part in the contract.
- `manifest.Action.role` (D158): the Cocoa editing selector (`undo:`, `redo:`, `cut:`, `copy:`, `paste:`) a macOS
  shell needs next to an Edit item's accelerator, set on the shared Undo/Redo/Copy/Cut/Paste block of every app and
  carried through `describe()`. Additive; GTK ignores it. First consumer: `clients/macos`. `clients/windows` reads
  the same `describe()` output via its own `generate_menu.py` copy but ignores this one field — Windows has no
  native selector to route it through (see `clients/windows/README.md`).
