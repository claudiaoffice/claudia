# The web app (demo v0)

The web client lives in `web/` (Nuxt 4, single-page, no server-side rendering). It talks to the server only through
the versioned protocol described in {doc}`server`: there is no other back door.

One server serves one app (`--model`; the default is the workbook), and the web app shows whatever the server says the
document is (`welcome.app`): **computes** (a table, below) or **composes** (a text, see [Writing in composes](#writing-in-composes)).
The header, menus, side panel, open dialog and colours are shared; each app has its own colour (`data-app` on the
page, `tokens.css`).

## What it shows (computes)

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

## Writing in composes

`./start.sh --app composes` serves texts (documents in `./demo-docs-composes`, because a directory holds one app's
documents). The text view lives in `TextWorkspace.vue` and `TextEditor.vue`; its state is `lib/text-session.ts`
(`TextSession`, next to the workbook's `Session`, both built on `lib/base-session.ts`) and `lib/blocks.ts` (pure:
the paragraphs, the events that change them, where a caret or zone goes when somebody else writes).

* **Paragraphs with named styles** (Body text, Title, Heading 1/2, Quote, Remark, Definition). You mark text by what
  it is for (D62); Enter after a heading starts body text. No bold/italic yet.
* **Typing** is shown at once and sent when the word ends (a pause or any other action sends it too), so a word is a
  step in the history. Text appears in the document only when the server's events say so; the browser never edits the
  page itself. Everything goes through `replace_text` (a range, which may span paragraphs, replaced by text).
* **Colleagues**: their caret with their name and the ± 3 words around it (D11), which are locked for everybody else
  while they write there. Your own zone is held the same way.
* **Who wrote what** (View ▸ Show who wrote what): runs coloured by author; text that came from a suggestion is
  dotted and says whose it was.
* **The assistant only suggests** (D63). `@ai review this text` (or `check this paragraph`) makes suggestions; they are
  listed above the history, marked in the text, and accepted or rejected by a person. Accepting is an ordinary edit by
  the accepter. A suggestion whose text changed cannot be accepted any more.
* Flow and Page views, Save as Markdown (current text only), Insert sample text (Tools) to try the assistant.

Known gaps: bold/italic and lists, windowing of very long texts (the whole text is loaded), an exact page layout
(Page is a sheet with margins), input methods are minimal (the composed text is sent when composition ends), and each
word is one undo step (the kernel has no grouping yet).

## Build and run

The quick way (Linux, macOS: `./start.sh`, Windows: `start.cmd`) builds the web app when it is missing, starts the
server and opens the browser. Documents are kept in `./demo-docs`.

```bash
./start.sh                       # or: uv run python scripts/start.py
./start.sh --dir ~/claudia-docs --port 9000 --no-browser
./start.sh --rebuild             # build the web app again first
./start.sh --tls                 # encrypted; the browser warns once about the server's own certificate
```

By hand (needs Node.js 22 or newer for the build):

```bash
cd web && npm ci && npx nuxt generate          # writes web/.output/public
cd .. && uv run python -m claudia_server --no-tls --dir ./demo-docs --web web/.output/public
```

Open <http://localhost:8765>, create a document (the creator is its owner), then share it and join from a second
browser to see presence, locks and the assistant working.

## Tests

```bash
cd web && npm test           # vitest: protocol client, workbook and text sessions, text replica, selection, people
npm run typecheck            # vue-tsc
npm run e2e                  # two real browsers against a running server (needs Playwright)
npm run e2e:composes         # the same for a text: URL=http://127.0.0.1:8766/ against a server started with
                             #   --model claudia_composes:TextModel --no-tls --web web/.output/public
npm run e2e:resilience       # starts its own server, restarts it, checks that both browsers come back
```

`uv run python scripts/check_debt.py` runs the web checks too (skipped when npm or `web/node_modules` is missing).
