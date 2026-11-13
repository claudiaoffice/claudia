# Changelog of the Linux client and the shell contract

Newest first. The shell contract has its own version (`clients/contract/`); this file lists both.

## [0.1.0] - unreleased

### Changed (one key table, every menu entry everywhere: UX-35, UX-36)
- Every menu entry has a key, the same in every app and every client (`manifest.py`, D340); only the language
  picker's entries have none. The keys stay clear of what browsers keep (Ctrl+N, Ctrl+W, Ctrl+T), of AltGr on Windows
  and of the desktop's own. New: Ctrl+Alt+N New, Ctrl+Alt+W Close Document, Ctrl+? Shortcuts (was F1), F1 How Do I…?,
  and keys for File ▸ Manage ▸, the View toggles, Format and Tools.
- `Action.key_owner` says who listens for a key (`KeyOwner`): the page in every client, the shell (Quit, About,
  Shift+F10), or the document view (Enter, Delete, Tab, the clipboard). GTK binds only the shell's own keys; the menus
  show every key through the GMenu `accel` attribute. Before, Ctrl+N, Ctrl+O, F1, Ctrl+F, F9 and the Ctrl+Alt keys
  were bound here and taken from the page; on Windows nobody listened for them.
- The menus have what the web menus have (UX-36): File ▸ Print… (composes, creates), Format ▸ List ▸ (every app, as on
  the web), Edit ▸ Insert ▸ Soft Hyphen / Non-breaking Hyphen (composes), Edit ▸ Image… and Chart…, Format ▸ Clear Cell
  Style, Tools ▸ Names… and SQL Query… (computes), Edit ▸ Image… and View ▸ Show Grid (creates). New page actions: the
  contract version is unchanged.


First slice of the native Linux client (epic 5).

### Added (alt text and decorative objects, BITV 1.1.1)
- Format ▸ Describe Object… (Ctrl+Alt+D, action `format.describe`) in claudia computes and claudia creates: the page
  opens its own dialog to describe the selected object or mark it as decoration. A new page action, so the contract
  version is unchanged; the macOS and Windows menus follow by regeneration.

### Added (computes: random numbers, alternatives, following)
- Tools ▸ Random Generator… (Ctrl+Alt+R), Resample Random Numbers (F9), Outcomes of This Cell… (Ctrl+Alt+O) and Follow
  Computation (Ctrl+Alt+F, checkable) in claudia computes (E6.21–E6.23); the macOS and Windows menus follow by
  regeneration. The drawing is the web page's own.

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
