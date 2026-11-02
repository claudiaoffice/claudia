# The web app (demo v0)

The web client lives in `web/` (Nuxt 4, single-page, no server-side rendering). It talks to the server only through
the versioned protocol described in {doc}`server`: there is no other back door.

## What it shows

* An open/create dialog with the documents of the server (`GET /api/docs`; `--no-list` hides them).
* The grid, a formula bar, undo/redo (per author, refused when a colleague wrote the same cell after you).
* A panel docked on the right with the **history** (every command: who, what, when) and the **chat**; `@name`
  mentions people, `@ai` asks the assistant.
* Presence: other people's cursors and locks are outlined with their colour and name.
* File ▸ Save makes a checkpoint; File ▸ Share lets an owner add people (`add_user`).
* A banner while the connection is lost; the app reconnects by itself and reloads what it shows.

The assistant in this demo is a **scripted stand-in** (`claudia_server.ScriptedEngine`): it understands a few
phrases (say `@ai help`) and says so when it does not understand. It edits through the same method table as everybody
else, so locks and roles apply to it. The real model replaces the engine (E3.6) without any change in the client.

Not in v0: formulas (typed text starting with `=` is kept as text), restoring checkpoints, objects and charts,
sliders, encryption of the file store, column resizing.

## Build and run

```bash
cd web && npm ci && npx nuxt generate          # writes web/.output/public
cd .. && uv run python -m claudia_server --no-tls --dir ./demo-docs --web web/.output/public
```

Open <http://localhost:8765>, create a document (the creator is its owner), then share it and join from a second
browser to see presence, locks and the assistant working.

## Tests

```bash
cd web && npm test           # vitest: protocol client, replica store, selection, people
npm run typecheck            # vue-tsc
npm run e2e                  # two real browsers against a running server (needs Playwright)
npm run e2e:resilience       # starts its own server, restarts it, checks that both browsers come back
```

`uv run python scripts/check_debt.py` runs the web checks too (skipped when npm or `web/node_modules` is missing).
