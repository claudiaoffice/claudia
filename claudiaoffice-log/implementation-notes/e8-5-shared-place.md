# E8.5, part 2: Shared on this computer (2026-11-25)

Branch `mac-installer`. Decisions D1622 (the service is a place of its own, found through a marker: built now) and
D1624 (the computer's administrators read the service's setup code; anyone else is told to ask one). The design is
`notes/e8-5-architecture.md`, part 2; the scenarios are `specs/desktop/shared-place.feature`, bound by
`tests/e2e/specs/test_shared_place.py` and the unit tests their tags name.

## What was built

| Where | What |
|---|---|
| `clients/neutralino/src/shared-service.ts` | `findSharedService(file)`: the marker's loopback origin and absolute state folder, or `null`; `setupCode()` read anew each time: the code, none, or "may not" |
| `src/platform/{host,macos,windows}.ts` | `sharedServiceFile(env)`: `/Library/Application Support/Claudia/service.json`, `%ProgramData%\Claudia\service.json` |
| `src/servers.ts`, `connector.ts` | `forPage` lists the service after her private place (`shared: true`), with the name a person gave it if any; `sanitize` drops a shared entry nobody named; `ServerBook.remember` does not remember the service |
| `src/core.ts` | `sharedService` option (found by the marker by default); `show` sends the service's `setupCode`, or `askAdministrator` |
| `src/core-protocol.ts`, `bridge.ts`, `shell-page.ts`, `contract.ts` | the `show` message's `askAdministrator`; the bridge asks one `setup()` at every hello instead of `setupCode()`; `welcome.ask_administrator` |
| `clients/contract/shell-contract.v1.schema.json` | optional `serverEntry.shared`, `welcome.ask_administrator` (additive, v1 stays) |
| `clients/linux/.../servers.py`, `contract.py` | accept both fields (Linux has no service, Q21) and keep the same `sanitize` rule |
| `web/app/lib/server-bookmarks.ts` | `named`: "Shared on this computer" for a `shared` entry unless renamed, also once it has an administrator; `isBookmark` takes `shared` |
| `web/app/lib/setup-code.ts`, `shell-bridge.ts`, `FirstAdminSetup.vue` | `rememberAskAdministrator` from each welcome; the code field's hint says to ask an administrator of this computer |
| `web/app/components/OpenDialog.vue` | the administrator's name no longer replaces the shared place's name |
| `packaging/windows/claudia.iss` | the marker written with the service component and removed on uninstall; `state` for `SYSTEM`, `Administrators` and `LocalService` only; the component's new wording, in German too |
| `.github/workflows/windows.yml` | the install test checks the marker, the state folder's rights, and the marker's removal |
| `po/` | the administrator sentence in German; `de.json`, `xx.*`, both `claudia.mo` derived again |

## Deviations from the architecture note, and why

* **The service's state folder is `%ProgramData%\Claudia\state`**, as its `claudia-service.xml` starts it
  (`--state-dir`); the note said `state\service\admin`, which is its log folder. The installer restricts the whole state
  folder (it also holds the administrators' password hashes), not only `admin`.
* **Users lose read access instead of Administrators gaining it.** Administrators already have it on `%ProgramData%`;
  what makes "may not" true for everyone else is taking away what `Users` inherit (`/inheritance:r`).
* **`sharedServiceFile(env)` takes the environment** like `claudiaFolder` (for `%ProgramData%`, and for the tests).
* **The bridge's `setupCode` option became `setup`**, one value with the code or `askAdministrator`: the two travel
  together and exclude each other.

## What the code review changed (2026-11-25)

* **The setup code is read, not `access()`-checked** (`setupCodeAccess` in `private-server.ts`, shared by both places):
  on Windows Node's `access()` ignores ACLs, so a person who may not read the file would have got "none" and the usual
  hint instead of "ask an administrator". EACCES and EPERM are "may not".
* **A broken service file is logged** (`findSharedService(file, log)`); a missing one is not (no service is normal).
* **One `Setup` type** (`core.ts`) for `setupCode` / `askAdministrator`; the schema (`not: required both`) and both
  parsers refuse a `welcome` that has both.
* **A rename that leaves the name as it was renames nothing** (`withRenamed`): opening Rename on the shared place and
  leaving made "Shared on this computer" her own name for it, untranslated and outliving the service.
* **"Service file", not "marker", in code**: the glossary's *Marker* is a list's bullet. The decisions keep the word
  as plain English.
* The tests of the two key risks (the service listed; the code given only to whom may read it) carry a
  `// must not break` comment, the new rule of `coding-standards.md`.

## Assumptions (say if they are wrong)

* A name a person gives the shared place is remembered under its origin; if the service is removed, that renamed entry
  stays in her list as a remembered server (as any server she renamed). An unrenamed one goes with the service.
* A changed service port (someone edits `claudia-service.xml`) needs the marker changed by hand; the installer writes
  8765, as the configuration it installs.
* The setup page keeps the code field when she has to ask: an administrator may tell her the code.
* "Must not break" is marked by a comment above the test until the test-quality branch (D1660–D1679) sets a form.
* Reinstalling without the service component leaves an earlier service's marker until the uninstall (as it leaves the
  service itself: Inno Setup does not remove a component that is no longer chosen).

## Use it before delivery (2026-11-25)

A real claudia server stood in for the service (`python -m claudia_server … --port 18765 --no-tls`, its own state and
documents folders, `admin/` 0700 as the server makes it), with a real service file pointing at it, and the built core
(`clients/neutralino/dist`) run as root (an administrator of this computer) and as a second account made for the run:

| Who | Her places | The service's page is told |
|---|---|---|
| root | Private on this computer, Shared on this computer | `setupCode` (the server's real code) |
| a second account | Private on this computer, Shared on this computer | `askAdministrator` |
| a second account, service file naming 192.0.2.7 | Private on this computer (the file is logged) | — |
| a second account, no service file | Private on this computer | — |

The run found that **a desktop window cannot connect to a server of all three apps**: the connect check of both shells
(`connection.ts` / `connection.py` `interpret`) wants `app` in `/api/docs`, and a server of several apps (D430), like the
service, says `"app": null, "apps": [...]` -- "That does not look like a Claudia server". Older than this branch (the
service was never connected to before; a demo server of all three apps has the same fate); reported with part 2, not
fixed yet. The run went on with the check stood in.

## What could not be run here

* The Windows installer and its CI install test (no Windows here): `claudia.iss` and `windows.yml` are checked by
  `tests/test_windows_packaging.py` and a YAML parse only. Inno Setup's order of `[Run]` and `ssPostInstall` does not
  matter for the marker (the apps read it at start).
* The "may not" case of `shared-service.test.ts` (this machine runs the tests as root, who reads everything); it runs in
  CI's Ubuntu job of the Neutralino client, as a normal user (it is skipped on Windows, which has no `chmod 000`).
* Two real accounts on one Mac or PC: the browser scenarios stand a loopback server in for the service.
