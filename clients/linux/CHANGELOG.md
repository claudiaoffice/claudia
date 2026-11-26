# Changelog of the Linux client and the shell contract

Newest first. The shell contract has its own version (`clients/contract/`); this file lists both.

## [0.1.0] - unreleased

### Changed (E5.23, E5.24, D1643–D1656): the menus are the workbook's, and they show what fits
- The menu definition moved to `clients/contract` (`claudia_menus.manifest`, D1643) and is the owner's workbook
  `claudiaoffice-log/notes/claudia-menus.xlsx`: entries, places, keys and when each fits (D1605). File ▸ Save, Assign
  New Owner…, Accept Ownership…, Leave Document… and Delete From Server… left the menus; File ▸ Manage ▸ My Role…
  (Ctrl+Shift+Alt+L) leads to the three role steps, and a document is deleted from the front page's list (D1656).
  Shift+F10 is no longer the shell's own key.
- The shell contract's `action_state` may carry `visible` per action and `empty`, the menus of the bar with nothing
  left and the sentence that says why (both optional, so version 1 stays, D1645). The shell leaves out what the page
  leaves out (`manifest.visible_only`, which `for_start` now uses), puts the greyed line into a menu with nothing
  left, and keeps an open menu as it opened until it is closed (D1603).

### Added (SEC-12, D1373): the setup code of the desktop's own server
- The shell contract's `welcome` may carry `setup_code` (optional, so version 1 stays): the setup code of the shell's
  own server while it has no administrator, read in its state folder at every `hello`, and only for a page of that
  server. Its settings pages then do not ask the person for it. `DesktopServer.setup_code`, `read_setup_code`,
  `setup_code_for_page`; `contract.welcome(setup_code=)`; `Bridge(setup_code=)`.

### Added (E3.14)
- File ▸ Manage ▸ Redact History… (Ctrl+Shift+F8), in every app: owners and editors pick what to redact in History
  & Chat (D727); viewers see it off.

### Changed (E1.10, D783, D786)
- Format ▸ All Styles… says in its description that styles can be deleted and hidden there. No new entry and no key: the page's own dialog does the work (D301), in the macOS and Windows client as well.

### Added (E9.32, D1208, D1213)
- Claudia Composes: Insert ▸ Table… (Ctrl+Shift+F) and, in Edit, Row ▸ and Column ▸ (the keys computes has), Sort ▸
  Ascending (Ctrl+Shift+X) and Descending (Ctrl+Shift+Y), Merge Cells (Ctrl+Shift+G), Split Cell (Ctrl+Shift+H) and Table
  Options… (Ctrl+Shift+L); the page reports them off while the caret is not in a table. Row ▸ and Column ▸ are one helper
  for computes and composes.

### Added (step H)
- Insert ▸ Cross-Reference… (Ctrl+F2) and Edit ▸ Go to Target (Ctrl+Alt+Enter), in every app; computes shows them
  off.

### Added (E9.31)
- Insert ▸ Table of Contents (creates: Agenda), Ctrl+Alt+Shift+I, before Insert ▸ Container; computes shows it off.

### Added (E9.22)
- Format ▸ List ▸ Number Headings (creates: Number All Slide Titles, Ctrl+Alt+Shift+B, ticked while they are numbered)
  and All Numbering… (Ctrl+Alt+Shift+J). The mock-up's keys were taken: Ctrl+Shift+F8 is Present from This Slide's,
  and Ctrl+Alt+E is AltGr+E (€) on Windows.

### Added (D1024)
- Format ▸ Rotate ▸ Rotate Right 90° (Ctrl+Alt+.), Rotate Left 90° (Ctrl+Alt+,) and Rotate By… (Ctrl+Alt+Shift+Z) in creates. Ctrl+Alt+Z stays Replay History's, so Rotate By… takes the Shift.
- The menus of the macOS and Windows clients are generated again from the manifest: they had not been since the Insert menu was added.

### Added (D552, E6.24)
- Edit ▸ Rename Sheet… in computes and Edit ▸ Rename Slide… in creates (Ctrl+Shift+F11), after New Sheet and New Slide.
### Added (D627): Tools ▸ Pivot Table… and the entries that work on one
- Claudia Computes' Tools menu has Pivot Table… (Ctrl+Alt+V), Pivot Fields (Ctrl+Shift+Alt+M), Value Field Settings… (Ctrl+Shift+Alt+U), Show Pivot Table as SQL… (Ctrl+Shift+Alt+Q) and Delete Pivot Table… (Ctrl+Shift+Alt+V); the generated menus of the macOS and Windows clients and the web key table follow the manifest.

### Changed (D504): the local server is on port 8765
- The shared local server listens on 8765, the port of `./start.sh`; a Claudia server of the same version already there
  is used, whoever started it. Another port only when something else holds 8765 (logged), or with
  `CLAUDIA_SERVER_PORT`. The e2e test gives its window a free port of its own.

### Added (D505): files dropped on the front page
- A file dragged from the file manager onto the window while the front page is shown is read by the window and sent
  to the page (shell contract v1, additive: `offer_file`, then `file_chunk`/`file_done`), which imports it. WebKitGTK
  does not hand such a drop to the page.

### Fixed
- File ▸ New and Open… on the front page now show what they did (D503): after a menu action the keyboard focus was not
  in the web view, so the field the page focused did not show it; the window now gives the web view the focus.

### Changed (D445, D434): the three apps share one local server
- The window no longer starts a server of its own app (`--model`, a new port each time) that ends with it.
  `desktop_server.py` finds or starts the one server of the suite: all three apps, `$XDG_DATA_HOME/claudia/documents`
  and `$XDG_STATE_HOME/claudia/server`, the port remembered in `desktop-server.json`, `--exit-when-idle 600`, started
  without the death signal so that it outlives its windows. Finding it runs on a thread (the window never blocks); a
  presence connection keeps it in use while a window is open and starts it again if it went away. The twin of the
  Windows and macOS clients' `desktop-server.ts`. Documents of the old per-app folders are not moved (D437).

### Fixed
- `welcome` now carries the window's app (D444); with the shared server the front page would have listed every app's
  documents.

### Added (D501, D502, D503)
- Shell contract v1, additive: capability `files` and the messages `pick_file`, `save_file` (`purpose`: `save` or
  `print`), `file_chunk`, `file_done` and `file_result`. A file travels in pieces of 36 KiB, so no message is over 64 KiB.
- The window chooses and saves the page's files with GTK's own dialogs (`files.py`, `window.GtkDialogs`): Open a
  File… works from the native menu too, and an export asks where to save and says where it went, instead of landing in
  Downloads. Print… opens the pages in the desktop's PDF viewer.

### Fixed (print on the desktop: E6.19)
- Claudia Computes had File ▸ Print… (Ctrl+P) on the web only: the desktop shells hide the web menu bar, so on the
  desktop the sheets could not be printed. It is in the menus of the Linux client and in the listing for macOS and
  Windows now, like in the other two apps.

### Added (passwords: D448)
- File ▸ Manage ▸ Change Password… (Ctrl+Alt+Shift+W), a page action in every app; in the macOS and Windows menus
  through the generated listings.

### Added (one server for all three apps: D444)
- Shell contract v1, additive: `welcome` may carry `app`, the app this window is. On a server of several apps the
  page then lists only that app's documents and refuses files of another kind. A shell that leaves it out gets the
  page of a browser tab.
- Shell contract v1, additive: `hello` may carry `view` (`start` or `document`, D447). The window shows the front
  page's short menu (`manifest.for_start`, `on_start`: File New/Open/Open a File/Quit, View Dark Mode, Config App
  Language, Help About) and switches the other actions off; a document, or a page that does not say, gets the whole
  menu. The listing for macOS and Windows carries `start` on every action.

### Changed (one key table, every menu entry everywhere: UX-35, UX-36)
- Every menu entry has a key, the same in every app and every client (`manifest.py`, D360); only the language
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

### Added (presenter mode, E10.2)
- Creates' menu manifest: View ▸ Present from the First Slide (`F5`, `Ctrl+Alt+P`), Present from This Slide
  (`Shift+F5`, `Ctrl+Shift+F8`), Speaker Notes (`Ctrl+Alt+V`, checkable); Edit ▸ Plan the Time of This Slide…
  (`Ctrl+Alt+Shift+T`). Page actions, no contract change; the German texts are in the catalog. The two-window show and
  fullscreen from the shell (a `create` handler for new windows) wait for the spike's runs (D345).

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
