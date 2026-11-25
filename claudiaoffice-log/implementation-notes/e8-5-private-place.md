# E8.5, part 1: Private on this computer (2026-11-25)

Branch `mac-installer`. Decisions D1620 (her apps use only her own server, proven by a key), D1621 (her own port), D1622
(the service is a place of its own: decided, built in part 2), D1623 (the page names the places). Fixes CODE-99 and
CODE-100 (in review). The design is `notes/e8-5-architecture.md`, part 1; the scenarios are
`specs/desktop/private-place.feature`, bound by the tests their tags name and by `tests/e2e/specs/test_private_place.py`.

## What was built

| Where | What |
|---|---|
| `packages/claudia-server/.../owner_proof.py` | `--owner-key-file`, `GET /api/owner?challenge=…` (loopback only; the HMAC covers the port from the socket) |
| `clients/contract/private-port.vectors.json` | the expected ports and proofs, worked out once with the standard library; read by the server's, the TypeScript and the Linux client's tests |
| `clients/neutralino/src/private-port.ts`, `owner-key.ts` | her port (uid; on Windows the profile folder), her key and the proof |
| `clients/neutralino/src/private-server.ts` | was `desktop-server.ts` / `DesktopServer`: her own port first, a server there only when it proves to be hers, `instead` while her port is held |
| `src/platform/{host,macos,windows}.ts` | `account(home)` |
| `clients/linux/.../private_server.py`, `private_port.py`, `owner_key.py` | the Python twin (uid only) |
| `web/app/lib/server-bookmarks.ts`, `shell-bridge.ts` | `named` ("Private on this computer"), `defaultLabel` ("Shared on this computer" for a loopback server in a plain tab), in her language |
| both shells | their own label for the private entry is "Private on this computer" (the page renames it anyway) |
| `po/` | the two names and the two reworded Linux messages, in German; `de.json`, `xx.po`/`xx.json` and both `claudia.mo` derived again |

## Deviations from the architecture note, and why

* **Her usual port is not stored**, it is worked out at every start (it is the same every time). `desktop-server.json` holds
  only `{"instead": N}` while her port is held by something else, and is removed once her server is back on her port. An
  older file (`{"port": N}`) is not read. One file and one rule less.
* **The walk of her range is `walkFrom` / `walk_from`** (after her port, then from the first), and `freePort` /
  `server.free_port` are gone. A first version took any free port; the code review showed that two windows starting at
  once then go to two ports and the loser fails, so every window now tries the same ports in the same order.
* **`writePort(…, 'exclusive')` is gone** (TypeScript and Python): nothing but its own tests used it since the server
  learned to lose a race by itself (D435).
* The messages of the version and app checks now say "Your Claudia server…", since only her own server is compared.

## What the code review changed (2026-11-25)

* **Her server still running on the `instead` port** is used before a new one is started on her own port, which has come
  free (a second server would die on her documents' lock, D435, and the window fail after 30 s).
* **The walk** (above), so two windows that start at once meet on one port.
* **Her own server from before E8.5** (on 8765, with no key) still holding her documents after the update: her new server
  exits on the folder's lock; the apps recognise the server's words ("another Claudia server uses …",
  `folder_lock.py`) and say that it is most likely her own of an older version, which stops by itself ten minutes after
  its last window. This is the scenario "My own server of an older version is still running after an update" for the
  update to this version; from then on the version check of her own, proven server says it.
* **The key is written whole under another name and linked into place**; when another of her windows was first, its key
  is the one (`ownerKey(state, make)` / `owner_key(state, make=…)`, tested by letting `make` play the other window).
* **A window whose server went away starts it again where its page is** (`ensure(stay)` / `_ensure(stay)`), not on her
  own port that may have come free meanwhile.
* `isOwnedBy` / `is_owned_by` take the port only; `_find_on` returns a `Literal`; the challenge helper is private;
  changelogs, READMEs and `docs/server.md` updated.

## Assumptions (please check)

* `process.getuid()` is the account number on a Mac (it is, for the person who runs the app); on Windows `os.homedir()` is
  the profile folder of the person who runs it.
* A Windows profile folder may differ only in case between two spellings (`C:\Users\Anna`, `c:\users\anna`): lower-cased
  before hashing.
* The `instead` port is written by the window that starts the server there; a second window that starts at the same
  moment loses the race as before (D435) and finds the winner, which must prove to be hers.

## Tests

* Server: `tests/test_server_owner.py` (13).
* macOS/Windows client: `tests/private-port.test.ts` (15), `tests/private-server.test.ts` (rewritten: a fake computer with
  people, shared servers, programs, silent holders and the documents' lock; 36 with the real health check, port check and
  setup code); `local-server.test.ts`, `server.test.ts`, `connector.test.ts` updated. All 572 pass.
* Linux client: `tests/test_private_port.py` (11), `tests/test_private_server.py` (rewritten, same scenarios),
  `test_launch.py`, `test_server.py`, `test_connect_flow.py` updated; `test_e2e.py` now also checks the real proof of the
  real server with the key in her state folder.
* Web: `tests/server-bookmarks.test.ts` (the names, in English and in German from `public/i18n/de.json`),
  `tests/shell-bridge.test.ts`.
* Browser: "A claudia server on this computer, opened in a browser tab" (`@core @firefox`), run in Chromium here.

## What could not be run here

* **Firefox**: this workspace has only Chromium; the browser scenario is tagged `@firefox` for the owner's run.
* **The Linux client's GTK tests** (`test_e2e.py` with the real proof, `test_webpage.py`): GTK does not load for the
  workspace's Python; CI's `linux-client` job runs them.
* **A real Mac or Windows PC, and two people logged in at once**: the two-people scenarios are checked on the fake
  computer of the unit tests (the agreed seams); nothing of macOS or Windows ran.
* The Windows installer's service with this change: the service no longer serves as anybody's own server; until part 2
  lists it, a person on Windows does not see it in her places (D1622 says so).
