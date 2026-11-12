# Changelog of the Linux client and the shell contract

Newest first. The shell contract has its own version (`clients/contract/`); this file lists both.

## [0.1.0] - unreleased

First slice of the native Linux client (epic 5).

### Added (all three apps, other servers, HTTPS)
- `claudia-computes` and `claudia-creates` beside `claudia-composes`: one shell for every app (`identity.names()`),
  one `.deb` with three start buttons (desktop entries, AppStream metadata and icons per app; the icons are those of
  the web app). `python3 -m claudia_shell_gtk APP` and `./start-client.sh [APP]` do the same from a checkout.
- `--server URL` on every command: no local server, connect to that one.
- Other servers from the start page: the page's "Connect to a server…" and Servers list ask the shell
  (`connect`), which checks the address (https; http only for this computer), the certificate and that the server runs
  the same app, then shows it in the same window. The shell keeps one list of servers per app, with **This computer**
  first (`servers` message). Certificates nobody vouches for can be trusted per origin (SHA-256 pin, `shell.json`);
  the dialog that asks is designed and still to be built.
- Shell contract **version 1, additive**: `connect`, `connect_failed`, `servers`; capabilities `connect` and `servers`;
  `hello.app` may be left out by a page that does not know its server's app yet.
- A GTK-free reader for the facts of a certificate (`x509.py`) and `shell.json` now holds the language, the servers
  and the trusted certificates, each saved without touching the others.

### Fixed
- A window showed the web app of an earlier visit after the server had been updated: WebKit keeps its HTTP cache
  between runs and decides for itself how long a page stays fresh. The page cache is now emptied before a server's
  page is loaded (D248).

### Changed
- Format menu of all three apps (D300, D301): **Apply Style…** first, a page action (`format.apply-style`) that opens
  the page's own style popover in its apply mode — the styles that fit what is selected, each drawn in its look. No
  new contract message: it is one action like All Styles….
- `ComposesApp`/`ComposesWindow` are `ClaudiaApp`/`ClaudiaWindow`; the window's menus are attached at runtime.
- The `.deb` is `claudia-office` (replaces `claudia-composes`).

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
