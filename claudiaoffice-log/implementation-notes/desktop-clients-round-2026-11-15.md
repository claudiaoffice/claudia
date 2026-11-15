# The three desktop clients: shared server, fonts, files, printing, the front page's File menu

Branch `clients`, 2026-11-15. Decisions D500–D505 (range D500–D519). The owner's list of what was wrong, and what
became of each point.

## `win-client` against main

`win-client`'s one commit ("Adapt win client to single server", 74f7698) is not on main by hash, but its content is: every
file it touches is identical on main or newer there (main has the CRLF-keeping config rewrite and the CI fixes on top).
Nothing was merged; merging it would only have reverted those fixes in `core-command.ts` and the CHANGELOG.

## One shared server on macOS and Linux (D445, D444, D434)

* **macOS** follows the Windows client file by file: `desktop-server.ts` (the same code; only the hint that names the
  operating system's tool differs: Activity Monitor), `server.ts` (`ServerStartError.exited`, the log quoted from this
  start's offset, `--exit-when-idle`, no `--model`, the child `unref`'d), `local-server.ts` and `paths.ts` (one folder of
  documents and one of state for the suite: `~/Library/Application Support/Claudia/{documents,state}`; the shell's own
  log stays per app), `core.ts` (lets go of the server), `contract.ts`/`bridge.ts` (`welcome.app`), `core-command.ts`
  and `launch.ts` (`enableInspector` off in the three configs, on for a `--debug` run only, put back afterwards), and the
  e2e script `web/e2e/macos-shell.cjs`, now the twin of `windows-shell.cjs`.
* **Linux** gets `desktop_server.py`, the Python twin: the same port file, health probe, version check, race with
  another window and presence connection. A window must not block, so `spawn()` finds or starts the server on a thread
  and the application polls `check_ready()` as before. The presence connection is a minimal WebSocket client (the
  standard library has none; it answers pings and notices the end). `server.py`'s `LocalServer` gets `outlives_shell`:
  the shared server is started without the death signal (`PR_SET_PDEATHSIG`) that tied a server to its shell. Folders:
  `$XDG_DATA_HOME/claudia/documents` and `$XDG_STATE_HOME/claudia/server`.
* **Found on the way:** the port file was written with an exclusive create and then filled, so a second window starting
  in the same instant could read it empty and pick a port of its own: two servers, and one window waiting 30 seconds
  for a winner on the wrong port (seen with the real server). It is now written whole under another name and linked into
  place, in all three clients. And the Linux bridge never sent `welcome.app` (D444); with one server per app that did not
  show, with the shared one the front page would list every app's documents.
* **Checked:** three `DesktopServer`s of the three apps started at once against the real `claudia_server` end on one port
  in about a second; the server stays while the presence connection is held past `--exit-when-idle`, and stops once let
  go. The macOS and Windows e2e scripts (real core, real server, the shell page in Chromium) pass, and the GTK e2e test
  under Xvfb with the real server and WebKitGTK.

## Fonts (D500)

The desktop server is started without `--fonts`, and nobody fetched fonts for it, so the print preview stopped with
"the server has no fonts to lay out with; its administrator can add some". computes' "“X” is not on this server; the
preview and the PDF use Y" works only when there is a Y. The owner chose to ship the starter set: `claudia_fonts/builtin/`
holds exactly the files of `starter.lock.json` (a test compares them by SHA-256), `builtin_folder()` names it, and the
server reads it before `--fonts`/`STATE_DIR/fonts`. A server started with nothing now says "fonts: 14 files in 5
families" and the preview lays out (checked in Chromium against a server with no fonts of its own). The Docker image no
longer fetches the set. `scripts/start.py` and the CI job still fetch it into a folder: harmless (the same files are not
reported twice), and left for a cleanup.

## Files through the shells' dialogs (D501)

Contract v1, additive: capability `files`; `pick_file`, `save_file` (with `purpose: print`, D502), `file_chunk`,
`file_done`, `file_result`. The schema, the Python and the TypeScript checks agree (tests judge each message by both).

* **Web:** `ShellBridge.pickFile`/`saveFile`/`handlesFiles`, `currentShell()` (the newest bridge that was welcomed),
  `acceptedExtensions()`; `lib/local-files.ts` (`chooseLocalFile`) for the three file inputs (Open a File…, Insert Image
  in creates and composes, in computes); `lib/download.ts` saves through the shell when it can and returns what became
  of the file; the two export dialogs say "Saved as …" and stay open on a cancelled dialog; Download PDF too.
* **Neutralino shells:** the shell page only passes pieces between the frame and the core (`file-protocol.ts`, no Node,
  because the shell page is a browser bundle). The core's `files.ts` (the same in both) reads and writes, and
  `dialogs.ts` is each OS's own: macOS runs NSOpenPanel/NSSavePanel through `osascript -l JavaScript` after
  `setActivationPolicy(accessory)` and `activateIgnoringOtherApps`, with AppleScript's `choose file` as the fallback;
  Windows runs the Windows Forms dialogs through PowerShell, owned by a top-most invisible form, with everything it needs
  in the environment and nothing put into the script.
* **Linux:** `files.py` (no GTK) and `window.GtkDialogs` (`Gtk.FileDialog`, `Gtk.FileLauncher`).
* **Not verified on a real Mac or Windows machine:** the panels coming up in front, the JXA property-style calls
  (`panel.runModal`), PowerShell's start-up time (about a second before the dialog). The e2e scripts show the round trip
  (page → shell page → core → page): there is no dialog to show on the Linux test machine, and the page says so.

## Printing from a window (D502, proposal)

With fonts in place the next wall was Print… itself: the preview prints its PDF in a hidden frame, which a desktop web
view cannot. In a window the PDF now goes to the shell, which opens it in the computer's PDF viewer; the bar says so.

## The front page's File menu (D503, proposal)

The three entries did run. New and Open… only moved the focus, invisible in a window whose page did not have it; Open a
File… clicked a file input from a script, which no web view allows. Now New empties the Document field, focuses it and
marks the new-document part of the form; Open… focuses and selects the search field; Open a File… goes through D501. The
Neutralino shell pages give the frame the focus before they send a menu action. Checked in the GTK e2e test and in both
Neutralino e2e scripts.

## Second pass: the empty window, port 8765, Linux Open and drops (D504, D505)

* **The empty window** (Windows after a fresh checkout and build, a Mac at its second start). The servers were not left
  running by mistake: D445 wants the shared server to outlive its windows. But `start.sh`/`start.ps1` and the launchers
  build the web app again at every start, and Nuxt's inline script (its config) gets a new hash with every build. The
  server computed the hashes of its Content-Security-Policy once, when it started, so the server from the first start
  refused the second build's inline script, and the page stayed blank (reproduced: CSP violation in the console). The
  server now reads the hashes again whenever an `*.html` of the web folder changed name, time or size
  (`WebScriptHashes` in `security_headers.py`), with a test that rebuilds the web folder under a running app. A Windows
  machine that had not been restarted still had such a server; so did the Mac after its first start. Not covered: a server
  started from *another checkout* keeps serving that checkout's web folder until it stops; the version check does not
  tell checkouts apart.
* **Port 8765 (D504).** `desktop-server.ts` (both) and `desktop_server.py`: probe 8765 first (and a remembered other
  port); a Claudia server there is used after the version check; when 8765 is free the server starts there; only a
  non-Claudia listener sends it elsewhere. `CLAUDIA_SERVER_PORT` overrides, and all three e2e runs set it to a free port
  so a developer's `./start.sh` does not get in the way. Checked with the real server: two `prepare_server` calls (two
  apps) without the variable end on `http://127.0.0.1:8765`, `desktop-server.json` says 8765.
* **Linux File ▸ New / Open….** The page did run the action (the e2e test showed it), but after a GTK menu the keyboard
  focus was not in the web view, so the focused field did not show. `window._focus_page` grabs it on idle after every
  menu action, as the Neutralino shell pages do. In the owner's screenshot New already showed; Open… did not.
* **Linux drops (D505).** A `Gtk.DropTarget` for `Gdk.FileList` on the window, in the capture phase (the web view
  would otherwise consume it), accepting only while the front page is shown; `files.offer(path)` sends `offer_file`
  and the pieces; `ShellBridge.onFileOffered` hands the `File` to `OpenDialog.takeFile`. Tested in `test_window.py`,
  `test_files.py`, the contract tests (TS and Python) and `shell-bridge.test.ts`; a real drag from Nautilus is not
  automated (no file manager on the test machine).

## Left open

* The macOS crash at quit: the owner sends a crash report. Since this round the core no longer stops the server when
  the window ends (it only closes its presence socket), which changes what happens at quit.
* `print.cjs` (web e2e) waits for a recovery-key dialog that a `--model` server no longer shows on main; not touched.
* `./start.sh` and the desktop apps now want the same port: with a desktop server on 8765, `./start.sh` fails to bind
  until that server has stopped by itself (D504's notes). If that gets in the way, `start.sh` could use a running server
  of the same version instead of failing.
* The shells still let WebKit/WebView2 handle a download the page did not route through `saveBlob` (none known).
