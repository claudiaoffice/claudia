# Linux client (E5), first slice: Claudia Composes

Written 2026-11-03; moved here 2026-11-05. What was built for the native Linux client of **composes**, how it was
checked, what deviates from the plan, and the decisions that came from it. The decisions were originally proposed as
D97–D103 and collided with the typesetting decisions of the same numbers; they are now **D113–D119** in
`decision-log/`.

Code: `clients/linux/` (package `claudia-shell-gtk`) and `clients/contract/` (the shell contract). Human
documentation: `clients/linux/README.md` and `clients/contract/README.md`, both also in the Sphinx docs.

## What exists

- `claudia-composes`: a GTK 4 / libadwaita window with the native menus **File, Edit, Tools, Help** in the header bar,
  a History and Chat toggle, `Adw.AboutDialog`, application id `de.claudiaoffice.composes`, a desktop entry, an icon
  and AppStream metadata.
- A **local server per window**: started without blocking the window, shown when `/api/health` answers, ended with the
  window and when the shell dies (its own process group, `PR_SET_PDEATHSIG`; tested with `kill -9` of the shell).
- The **shell contract v1** as a JSON schema with the Python side (`contract.py`, `bridge.py`): `hello`, `welcome`,
  `action`, `action_state`, `error`; a 64 KiB limit; unknown types ignored; version negotiation.
- A **page adapter** (`data/shim.js`) that lets the *unchanged* web app take part in the contract (D117).
- Rules of the web view: an origin lock, external links to the default browser, permission requests denied, downloads
  to the Downloads folder under a safe name.
- Checks: ruff and mypy targeting 3.12, vulture, 180 tests (145 without GTK, 35 with GTK and a display, one of them an
  end-to-end test with the real server and the built frontend), Sphinx with warnings as errors, a Linux-only CI job,
  and the client's checks in the main quality gate.

Nothing in `web/` or `packages/` was changed. Changes outside `clients/`: the gate script, `pyproject.toml` (vulture
paths), `vulture_whitelist.py` (six entries with reasons), `docs/` and one CI job.

## Menu mapping (D4 natively, the web app untouched)

The web app has six menus (File, Edit, Format, View, Tools, Help); D4 has four. The Linux shell maps between them, and
the mapping lives in `manifest.py` (what is shown) and `data/webroutes.json` (which web item an action uses). A test
compares the routes with the labels in `TextWorkspace.vue`.

| Native menu | Native item | Carried out by | Web item |
|---|---|---|---|
| File | Open… (Ctrl+O) | page | File ▸ Close document (back to the Open dialog) |
| File | Save | page | File ▸ Save |
| File | Save with a Name… | page | File ▸ Save with a name… |
| File | Save As… (Ctrl+Shift+S) | page | File ▸ Save as Markdown… |
| File | Share… | page | File ▸ Share… |
| File | Quit (Ctrl+Q) | shell | |
| Edit | Undo, Redo | page | Edit ▸ Undo, Redo |
| Edit | Cut, Copy, Paste, Paste As Plain Text | web view | WebKit editing commands |
| Tools | Look of this Style…, All Styles… | page | Format ▸ Look of this style…, All styles… |
| Tools | Page View (checkable) | page | View ▸ Page (off side: Flow) |
| Tools | Show Who Wrote What (checkable) | page | View ▸ Show who wrote what |
| Tools | Ask the Assistant…, Review This Text, Review This Paragraph | page | Tools ▸ same |
| Tools | Insert Sample Text | page | Tools ▸ Insert sample text |
| Help | Help (F1) | page | Help ▸ Keyboard |
| Help | About Claudia Composes | shell | |
| Header bar | History and Chat (toggle) | page | View ▸ History and chat |

Choosing a style stays in the page's own style box in the toolbar. Ctrl+S, Ctrl+Z and Shift+F10 are handled by the
page and are not bound natively, because they would run twice.

**This table is the debt.** It is a click path between two menu structures that D4 and E5.1 say should be one
manifest (UX-09), and it has to be rewritten for every shell.

**Update, 2026-11-05:** a patch retiring this whole mapping (D121) — `webroutes.json`/`shim.js` deleted, the web app
speaking the shell contract directly, `manifest.py` rebuilt to the seven-menu schema of D120 — is delivered, not yet
committed. This table describes what is on `main` today; see `e5-1-e5-10-menus-and-accessibility.md` for the patch.

## Deviation from the plan

The first plan was a custom URI scheme for the bundled frontend (D43) plus `--allow-origin` on the local server. It
cannot work with the unchanged web app: `OpenDialog.vue` derives the server address from `location.host`, so the page
must be served from the server's own origin. The shell therefore starts the server with `--web <frontend>` on
`127.0.0.1` with a free port and shows that address (D115). The bundled frontend of D43 is still what is shown; the
server serves it. **Side effect:** the port changes with every start, so the page's `localStorage` does not survive a
restart.

## Compatibility notes (3.12 client, 3.14 server, WebKit)

1. `/usr/bin/python3` is the interpreter that has the distribution's PyGObject; another `python3` first in `PATH`
   (pyenv, uv, conda) usually cannot import `gi`.
2. libadwaita 1.5 is the floor (`Adw.AboutDialog`; Ubuntu 24.04 has 1.5.0). The spike machine had 1.10 and PyGObject
   3.58; the sandbox has 1.5.0 and 3.48.2. 1.6 widgets such as `Adw.Spinner` are avoided.
3. `claudia-client` needs Python 3.14 and depends on `claudia-core`, so the 3.12 shell cannot import it. TLS trust for
   remote servers is therefore not available to the shell; decide when remote servers come — a small 3.12-compatible
   trust module, or let the page do it.
4. The root ruff and mypy configurations target 3.14; the client has its own targeting 3.12 so that 3.14-only syntax
   cannot slip in. `uv run mypy` must be run with `--project` from `clients/linux`, or uv makes an environment there.
5. Sphinx autodoc of the GTK modules would need `gi` mocked; only the GTK-free modules are in the API reference.
6. `preexec_fn` is unsafe with threads, and GTK has some: a two-line launcher sets `PR_SET_PDEATHSIG` and then becomes
   the server. The signal is tied to the *thread* that started the process, so the server is started from the main
   thread.
7. WebKit URL patterns cannot name a port, so the user script is admitted for the host and checks `location.origin`
   itself.
8. WebKit's network session is shared by all views of a process: downloads must be filtered by view, and a page must
   disconnect from the session when its window closes. GTK emits `destroy` only at disposal, so the window releases
   its page on close and on shutdown.
9. WebKit's bubblewrap sandbox, GL and accessibility bus may not work in containers and CI
   (`WEBKIT_DISABLE_SANDBOX_THIS_IS_DANGEROUS=1`, `LIBGL_ALWAYS_SOFTWARE=1`, `GSK_RENDERER=cairo`, no D-Bus); only the
   tests set them.
10. The web page has a grid row for its menu bar; hiding it needs `visibility: hidden` and height 0, not
    `display: none` or removal.
11. The web menu's items exist in the DOM only while a menu is open, so the adapter opens and closes menus to read
    states and to click, waiting a tick after each step because Vue renders asynchronously. States are polled every
    750 ms.
12. Vite and Nuxt serve absolute `/_nuxt` paths: fine behind the server's `--web`, and a reason not to use a custom
    scheme or `file://`.

## Not verified (needs a real session)

Only Xvfb was available, and no D-Bus session bus. **Not checked:** a real GNOME session and Wayland, input methods,
screen readers, the portal file dialogs, the look under the dark style, high-DPI scaling, Flatpak, single-instance
behaviour, and a packaged install — the frontend and the 3.14 interpreter are not bundled yet. The CI job was written
but could not run here.

## Open points for the owner

- **Stable port or storage:** the port is random per start, so web storage is lost. Options: a fixed port per user, or
  the page not relying on `localStorage`.
- **Native Save As** and **Open** file dialogs, as a contract extension with a target path.
- **Single instance:** the application keeps GApplication's default uniqueness, so on a desktop with a session bus a
  second start should activate the first window; without a bus each start runs its own window and server. Untested.
- **Closing the last window** ends the server and the app, which is fine for now.
- **Translations:** labels are marked translatable, but no catalogue exists (D31, E5.7).
- **Housekeeping:** `uv.lock.rej` in the root and `web/dist` tracked although `.gitignore` names `web/.output`
  (CODE-07, CODE-02). A stray `claudia-composes.patch` has since been cleaned up.

## One shell for three apps, other servers and HTTPS (E5.8, 2026-11-10, branch `linux-client-complete`)

Decisions D241–D247 (D241–D244 confirmed by the owner, D245–D247 proposed). Mock-up: `mockups/connect-and-trust.svg`.

**What changed.**
- *Three apps.* `identity.names()` is the one table; `cli.py` (parse, `--server`, `--debug`, `--version`), `__main__.py`
  (`composes()`, `computes()`, `creates()`, `main()` for `-m claudia_shell_gtk APP`), `ClaudiaApp`/`ClaudiaWindow`
  (formerly `Composes…`), `launch.py` and `server.server_command` take an identity. `window.ui` has one menu button
  per menu id; `_attach_menus` gives each the menu of the app's manifest at runtime, so one GType serves all apps and the
  menus are built in the language installed when the window is made. `apps/computes` and `apps/creates` have desktop
  entries, AppStream files and the icons of `AppIcon.vue` (a test compares the shapes). One `.deb` (`claudia-office`).
- *Other servers.* New GTK-free modules: `servers.py` (addresses, the per-app list), `settings.py` (one `shell.json`
  with `locale`, `servers`, `trusted`, each saved without touching the others), `x509.py` (a small DER reader: subject,
  issuer, validity, names, self-signed, fingerprint), `trust.py` (pins), `connection.py` (`check`: scheme → reach and
  certificate → app, with a real or fake transport), `connector.py` (worker thread, newest request wins, the trust
  question, the server book). `bridge.py` and the contract learn `connect`, `connect_failed`, `servers`. The web start
  page (`OpenDialog.vue`) says hello to the shell, shows the shell's list and sends `connect`; in a browser nothing
  changes.
- *HTTPS.* The check runs `ssl` against the system's authorities first. If that fails with *unknown issuer* or *name
  mismatch* it connects again without verification, reads the certificate **of that connection**, and only then asks
  (or accepts a matching pin). `WebPage` accepts an untrusted certificate only if it is the pinned one and the failure
  is `UNKNOWN_CA`/`BAD_IDENTITY` (`NetworkSession.allow_tls_certificate_for_host`, WebKitGTK 6.0 — signature taken from
  the WebKit documentation; **not run here**).

**Verified here.** Unit tests for all GTK-free modules (certificates made with `openssl`), contract and schema,
packaging drift guards, `tests/test_connect_flow.py` — the real web app in headless Chromium, three real servers (two
plain http, one TLS with a self-signed certificate) and the real `Bridge`/`Connector`/`check`/`TrustStore`: this
computer is listed first, plain http to another computer is refused, a server of another app is refused naming both
apps, an unknown certificate connects only after it is trusted and is pinned, declining connects nowhere, the way back
to this computer works. Web: vitest (537), vue-tsc, eslint. `scripts/check_debt.py`: everything clean.

**Not verified (needs GTK, a display and WebKitGTK 6.0).** `window.py`, `app.py`, `webpage.py` and their tests
(`test_window.py`, `test_app.py`, `test_e2e.py`, `test_webpage.py` are written but could not run: this sandbox has no
GTK stack). Run `xvfb-run -a pytest -m gtk` and `xvfb-run -a pytest -m e2e` on a real machine. Also unchecked: that the
three `.desktop` and AppStream files validate (`desktop-file-validate`, `appstreamcli`; CI does it), the `.deb` build,
and a real self-signed server in WebKit.

**Open points for the owner.**
- The "Trust this server?" dialog (A) and "certificate changed" dialog (B) are not built; waiting for the mock-up to be
  agreed. Until then an unknown certificate is refused with an explanation (`certificate_invalid`).
- The check decides *Claudia server of the right app* **before** the certificate question (mock-up panel D has them the
  other way round).
- `certificate_invalid` has a message of its own that the mock-up does not show ("The certificate of {host} is not
  valid." / "…not issued by an authority this computer trusts.").
- Bare `localhost:8420` means https. A plain local development server needs `http://localhost:8420`; a local server with
  TLS (the server's default) needs nothing. Alternative: try https, fall back to http for loopback.
- Forgetting a trusted certificate (proposed: "Remove" on a server in the list; the list has no remove action).
- `AdminApp.vue` still bookmarks into the page's `localStorage`; in a shell that list is not shown.
- The "Manage…" button of a server is hidden for servers other than the current one in a shell (the admin pages are on
  the other origin and cannot be opened from here).
- `hello.app` optional (D246) and the package name (D247).
