# SEC-12: the first administrator needs a setup code (D1370–D1376, branch `sec-12-setup-code`)

Specs: `specs/server/administrators.feature` (24 scenarios). Mock-ups: `notes/mockups/sec12-first-administrator-setup-code.svg`
(panels 1–8), architecture: `notes/mockups/sec12-architecture.svg`. Tracker: SEC-12 (fixed), UX-61 (fixed, the wording
patch of this branch).

## What was built, and where

| Part | Where | What |
|---|---|---|
| The code | `claudia_server/setup_code.py` | `SetupCode` (12 Crockford base32 characters, `make`, `of`, `matches` in constant time, shown in groups), `normalize`, the file `admin/setup-code` (0600; `write_code`, `read_code`, `remove_code`) |
| Before the server listens | `claudia_server/admin_start.py` | `prepare_administrators`: checks `--admin`'s password file first, then the reset (`admins.json` moved aside, `admin/reset.json`), then `--admin`, then a code if there is still nobody; the banner lines. `ResetNote`, `AdminOptions`, `AdminStart` |
| The admin API | `admin_api.py` | `status.setup_code`; `setup` needs `code` (429 → 409 → 403 in that order, before any hashing); `POST /setup-code`; `GET`/`DELETE /reset-note` (signed in); tries counted under their own key of the gateway's `LoginThrottle` (`ADMIN_SETUP`) |
| Start options | `cli.py`, `hosts.py` | `--reset-administrators`, `--admin`/`CLAUDIA_ADMIN`, `--admin-password-file`/`CLAUDIA_ADMIN_PASSWORD_FILE`; the link (`_settings_link`: first `--allow-host`/`--tls-name`, else the address; behind a proxy https without a port; only with `--web`); `is_exposed(host, behind_proxy)` (D1374), `is_unspecified` |
| Container | `docker/entrypoint.sh` | `CLAUDIA_ADMIN` + `CLAUDIA_ADMIN_PASSWORD` → a 0600 temporary file → `--admin`, the variable unset before `exec` |
| Web | `lib/setup-code.ts`, `app.vue`, `lib/shell-bridge.ts`, `lib/admin-api.ts`, `lib/admin-session.ts`, `lib/admin-reset.ts`, `FirstAdminSetup.vue`, `AdminApp.vue`, `AdminLogin.vue`, `AdminAccessDocuments.vue` | the code from `#setup=` (taken off the address at once) or from `welcome.setup_code`, kept in sessionStorage for the tab; `codeField` decides none / from-link / typed; a given code is checked first; `setupRefusal` sorts 403/429/409; the reset note with Dismiss |
| Linux app | `desktop_server.py`, `bridge.py`, `contract.py`, `window.py`, `app.py` | `read_setup_code(state)`, `setup_code_for_page(shown, local, read)`; the bridge asks the window at every `hello` |
| macOS and Windows app | `desktop-server.ts`, `core.ts`, `core-protocol.ts`, `shell-page.ts`, `bridge.ts`, `contract.ts` | `readSetupCode(state)`; the core sends `setupCode` with `show` for its own server only, read whenever it shows it; the shell page hands it over in `welcome` |
| Contract | `clients/contract/shell-contract.v1.schema.json`, `README.md` | `welcome.setup_code`, optional, grouped form (version 1 stays) |

## Where the build differs from the architecture drawing

- **The reset note is not in `GET /status`.** That answer is public and the note names the old administrators; it has its
  own signed-in route, `GET /api/admin/reset-note`.
- **The throttle key lives in `admin_api.py`** (`ADMIN_SETUP`, next to `ADMIN_LOGIN`); `login_throttle.py` did not need
  a change.
- **The admin page makes a shell bridge of its own** (`AdminApp.vue`, view `start`): before, only the front page and the
  documents said `hello`, so the settings pages never got a `welcome` in a desktop app.
- **macOS and Windows hand the code over with `show`, not at every `hello`.** There the bridge runs in the window's page,
  which cannot read files; the core reads the code whenever it shows its own server (at start, and when the person goes
  back to "This computer"). The server cannot restart while the window holds its connection, so the code is the one
  of the running server; one that has gone stale since (an administrator was named meanwhile) is refused, and the page
  then asks for the code or turns to the sign-in.

## Assumptions

- The set-aside file is named with the time of the start, `:` as `-`, so with milliseconds:
  `admins-before-reset-2026-11-20T22-04-11.732Z.json`.
- `--admin` with an existing administrator changes nothing even if NAME is not one of them (the banner says so).
- The container's password file (`CLAUDIA_ADMIN_PASSWORD` → `mktemp`, 0600) stays in its temporary folder while the
  container runs: the server reads it at start, after the entry point has handed over with `exec`.
- Behind a proxy, the link in the banner names the first `--allow-host` with https and no port; the proxy's own port
  cannot be known.
- A code from a link that the server refuses stays in the field, with the sentence under it; a code from the desktop app
  that is refused is not shown (it was never the person's).
- "Open the link from the server's log" in the scenarios opens the link's path and fragment at the server itself, as the
  proxy would forward them.
- The scenario "Too many wrong codes make me wait" tries five codes, not four as drafted: with three free tries the
  fourth failure starts the wait and the fifth try meets it (Q2 of the review).

## BITV

The code field has a visible label (`<label for>`), its hint is tied to it with `aria-describedby`, it takes
`autocomplete="one-time-code"` and `aria-invalid` when refused, and its error is announced (`role="alert"`). The check
mark of a code from a link is decorative; its meaning is in the words next to it. The line on top of the sign-in and the
reset note are `role="status"`. Dismiss is a button reached with Tab. No divergence from WCAG 2.1 AA known; a
screen-reader run was not possible here (see below).

## Tests

- Server: `test_server_setup_code.py` (8), `test_server_admin_start.py` (16), new tests in `test_server_admin_api.py`
  (8), `test_server_cli.py` (9), `test_server_hosts.py` (1), `tests/test_docker_entrypoint.py` (3).
- Web: `setup-code.test.ts` (10), `admin-reset.test.ts` (2), `admin-api.test.ts`, `admin-session.test.ts`,
  `shell-bridge.test.ts`.
- Linux app: `test_bridge.py`, `test_contract.py`, `test_desktop_server.py` (2), `test_window.py` (1, needs GTK),
  `test_app.py`. macOS and Windows: `bridge`, `core`, `core-protocol`, `shell-page`, `desktop-server` tests.
- End to end: `tests/e2e/specs/test_administrators.py` starts a server of its own per scenario (`live.server`) and reads
  its log; the desktop app is played by a `window.webkit.messageHandlers.claudia` that answers `hello`.
  `web/e2e/admin-fonts.cjs` fills in the code, which `scripts/run_e2e.py` reads from the server's state folder.

## What could not be run

- Firefox (not installable here): the scenarios ran in Chromium only. None is tagged `@firefox`.
- The GTK window and application tests (no GTK in this container): `test_window.py`'s new test is written and skipped
  here, as are the other GTK tests; the GTK-free parts (bridge, contract, desktop server) ran.
- The desktop apps themselves were not started; their part was checked by their unit tests and by the browser playing
  the GTK app's bridge.
- A screen reader.
- The demo on Scaleway: `CLAUDIA_ADMIN` and `CLAUDIA_ADMIN_PASSWORD` are the owner's to set there (Q6).
