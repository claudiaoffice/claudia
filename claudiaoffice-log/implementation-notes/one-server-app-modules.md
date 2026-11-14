# One server, app modules (D430–D437)

Branch `one-server`, first of a series of patches (E3.12). Until now one server process served one app: `./start.sh
all` ran computes, composes and creates on 8765–8767, three origins, three document folders, three certificates and
three copies of the AI model. One list of all of a person's documents (the file-management design of 2026-11-13) was
impossible across three origins (D170). The owner decided to move to one server; there is no release yet, so nothing is
migrated (D437).

The patches, in order: **server** (this note), web client (after its screens are agreed), Linux shell, macOS shell,
Windows shell, then offloading heavy jobs to the worker pool (D436).

## What was built in the server patch (`claudia-server` 0.30.0)

* `packages/claudia-server/src/claudia_server/suite.py` — `Module` (an app: its `Hub` and its `UserDirectory`) and
  `Suite` (the modules of one server, in order; `module(app)`, `locate(id)`, `for_new(app)`, `listing()`,
  `max_documents`, `start`/`stop`). Each module keeps its own hub, so the one-thread rule of a hub (D16) and every hub
  test stay as they were. `APP_MODELS` names the apps and their document models.
* `hub.py` — `Room`: the document cap counted over all hubs of a server (D432). `Hub.max_documents` is now the room's;
  `Hub.share_room`, `Hub.count_known`. The hubs of a suite also share one worker pool (D134).
* `app.py` — `Gateway` works on the suite (`module_for`: the app in the address, else the first module that has the id,
  else `hello.app`, else the first module; D431). New addresses `/api/{app}/docs/{id}/ws`, `/api/{app}/docs`,
  `/api/{app}/protocol`, registered after every fixed `/api/<word>/…` route so that no router path is read as an app.
  `/api/docs` answers `{app, apps, documents}` (`app` is `null` on a server of several apps). `/api/presence` holds a
  socket that carries nothing (D434). `create_app` accepts a `Suite` or, as before, a `Hub` and its directory.
* `idle.py` — `IdleWatch` and `IdleMiddleware`: every request and socket is reported; `--exit-when-idle SECONDS` stops
  the server through uvicorn's `should_exit` (so documents are packed, on every platform). `cli.main` now runs
  `uvicorn.Server` instead of `uvicorn.run` for that.
* `folder_lock.py` — `FolderLock`: `flock` (`msvcrt.locking` on Windows) on `DIR/.lock`; a second server on the same
  folder refuses to start (D435).
* `sealed.py` — a store refuses to open, and does not list, a file whose manifest names another app.
* `admin_api.py` — `AiRuntime(models=…)`: one language model for every app with a lens (computes, creates), the
  stand-in for the others (`assistants_for`, `any_lens`). The settings routes work on the suite.
* `cli.py` — `--apps` (all three by default) and `--model` (one app, documents directly in `--dir`, as before; D433),
  mutually exclusive. With `--apps` each app's documents go to `DIR/<app>/` (D431).
* `scripts/start.py` — one server; `./start.sh <app>` opens `?app=<app>` (D433); documents in `.claudia/documents`,
  state in `.claudia/state`; old folders are named, never used.
* `docker/entrypoint.sh` — `CLAUDIA_APP` is optional; set, it starts a one-app server the old way.
* CI and `tests/e2e/test_greeting.py` — until the web client chooses the app by address, the browser scripts run
  against three one-app servers started with `--model` on 8765–8767 (the bridge is removed by the web patch).

## Things to know

* **The web client still uses the old address.** It creates documents at `/api/docs/<id>/ws`, which on a server of
  all apps makes a workbook unless `hello.app` says otherwise. The start page greets according to `/api/docs` `app`,
  which is `null` now, so it falls back to the first listed document's app. The web patch fixes both; `?app=` in the
  address is what `./start.sh <app>` already opens.
* **Two browser scripts fail on unchanged `main` too**, here (Chrome 156 standing in for Playwright's Chromium):
  `e2e:search` times out in `waitSummary`, and `e2e:keys` finds no shortcut next to the "Image…" menu entry. Not
  caused by this patch and not investigated yet; `e2e`, `e2e:composes`, `e2e:slides`, `e2e:resilience`,
  `e2e:recovery` and `tests/e2e` pass with it.
* **Long names on the front page (fixed after the owner's first try, 2026-11-14).** Grid columns of `1fr` and an
  implicit grid track in `Modal.vue` grew to the longest unbreakable name, pushing the form out of the card and the
  import dialog past the window; the page had `min-height` and so never scrolled to "Or start a new one". Now:
  `minmax(0, …)` columns, a two-line clamped name with the details underneath, the import dialog's title is
  "Open a file" (the name is shown and wraps below it), and `.open` has a fixed height with `overflow: auto`. Adding to
  a collection was only possible after choosing a document from Mine; every row now has a bookmark button with the
  collections as a checkbox menu (in the flow under the row: the lists scroll, a floating menu was cut off) and rows
  can be dragged onto a collection. `entriesOf` shows a document put in from the place's list even if it was never
  opened from this browser.
* **Imports are not lazy yet.** `claudia_server` imports every app package, so a server of one app still loads all
  three. That matters once modules run in their own processes (D436) and is done there.

## Risks kept in E3.12

One module's crash or long computation affects every app until module workers exist; a server update restarts every
app's sessions; `/api/docs` reads every manifest on the event loop and the list is now three apps long; old bookmarks
to 8766/8767 stop working; restarted module workers will lose pending keys, presence, locks and render jobs (the
journal keeps every edit).
