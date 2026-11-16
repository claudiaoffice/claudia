# The web app (demo v0)

The web client lives in `web/` (Nuxt 4, single-page, no server-side rendering). It talks to the server only through
the versioned protocol described in {doc}`server`: there is no other back door.

One server serves all three apps (D430), and the web app shows whatever the server says the document is
(`welcome.app`): **computes** (a table, below) or **composes** (a text, see [Writing in composes](#writing-in-composes)).
The header, menus, side panel, open dialog and colours are shared; each app has its own colour (`data-app` on the
page, `tokens.css`).

## The front page and File ▸ Open (D443)

The page a server greets with (`OpenDialog.vue`) and File ▸ Open… (Ctrl+O, the same component in a dialog):

* **My places** on the left: the servers of this browser (or of the desktop shell), "This computer" for a local one,
  "+ Connect to a server…". **Collections** below: groups a person makes of documents from any place. A document
  goes into a collection with the bookmark button at the end of its row (Mine or the place's list: a menu of the
  collections with a tick for each it is in, and "New collection…"), or by dragging its row onto a collection.
* **Search** (Ctrl+F) over Mine and the place shown, by name; **Open a File…** (Ctrl+Shift+O, or drop a file on the
  page) for Word, Excel, PowerPoint, OpenDocument and Claudia files (`ImportDialog.vue`, D438–D442).
* **Mine** on top: the documents opened from this browser, on any place (`lib/mine.ts`); then every app's documents of
  the place, each with its app's icon and name, and an app filter.
* On the right, open a document with a name and password; **Create document** asks for Table, Text or Slides first on
  a server of several apps.
* A document opened from File ▸ Open… replaces the one in the window (`lib/switch-session.ts`).
* **In a desktop window** (D444) the shell says which app the window is (`welcome.app`): the page lists that app's
  documents only (place, Mine, collections), has no app filter and no choice of kind, offers only that app's formats
  in Open a File…, and refuses a file of another app ("This is a table. Open it with Claudia Computes."), by its name
  before uploading and by what the server read in it after. The native menu's File ▸ New, Open… and Open a File…
  work on the front page too. File ▸ Open… in a document borrows the document's bridge (`shellBridge`) instead of
  making a second one.
* **Opening a file** (D446): the import dialog comes as soon as a file is chosen or dropped, with one bar in three
  parts — sending (measured, `sendFile` in `lib/open.ts` over `XMLHttpRequest`), reading on the server and opening
  (not measurable, so moving stripes); `lib/import-progress.ts` says what the bar shows. Open waits for the file.
* **The front page says it is the front page** (`hello` `view: "start"`, D447), so a desktop app shows its short menu,
  and answers File ▸ New, Open…, Open a File…, View ▸ Dark Mode and Config ▸ App Language, reporting the ticks. A
  document says `view: "document"`.
* **Files in a desktop window** (D501, D502, D503): a shell that offers `files` chooses and saves files with its own
  dialogs. `lib/local-files.ts` (`chooseLocalFile`) asks it for Open a File… and Insert Image (the file input's dialog
  in a browser tab), `lib/download.ts` (`saveBlob`) hands it every file the page saves and says what became of it
  (`saved` with the path, `cancelled`, or `downloaded` in a tab); the export dialogs show "Saved as …". Print… in the
  preview hands the PDF to the shell, which opens it in the computer's PDF viewer. `currentShell()` is the bridge of the
  page shown now. On the front page File ▸ New empties and focuses the Document field and marks the "start a new one"
  part; Open… focuses the search field. A file the shell offers (`offer_file`, D505: dropped on a Linux window, whose web
  view keeps it from the page) reaches the front page through `ShellBridge.onFileOffered` and is imported like a drop.
* **Passwords** (D448): every password field is `PasswordInput.vue`, with an eye that shows and hides what was typed
  (starts hidden; attributes go to the input). File ▸ Manage ▸ Change Password… (`ChangePasswordDialog.vue`,
  `BaseSession.changePassword`, the protocol's `change_password`) changes the person's own password; a refusal is said
  in the dialog. `npm run e2e:passwords` checks both in a browser against a real sealed server.
* The front page holds the presence socket (`lib/presence.ts`, `/api/presence`, D434, D445) while it is shown, so a
  server started with `--exit-when-idle` knows it is in use; a dropped socket comes back after 1, 2, 4… s (30 s at most).
* Long names do not stretch anything: a row shows the name on up to two lines (the whole name as its tooltip), the
  columns and dialogs keep their width, and the page scrolls when the window is short.

## What it shows (computes)

* An open/create dialog with the documents of the server (`GET /api/docs`; `--no-list` hides them).
* The grid, a formula bar, undo/redo (per author, refused when a colleague wrote the same cell after you).
* A panel docked on the right with the **history** (every command: who, what, when) and the **chat**; `@name`
  mentions people, `@ai` asks the assistant.
  Above the chat box a switch, **Act at once | Suggest first**, says how the AI treats *your* requests in *this*
  document (D262). It is kept in the browser (`lib/ai-mode.ts`, one key per server and document), is *suggest* until
  you choose, and goes with every chat message as `ai_mode`; a colleague can choose differently.
* Presence: other people's cursors and locks are outlined with their colour and name.
* File ▸ Save makes a checkpoint; File ▸ Share lets an owner add people (`add_user`) and make a new recovery key (`new_recovery_key`). A new document shows its recovery key once, before it opens (`created` in the answer to `hello`); "I forgot my password" on the start page comes in with it (`hello` with `recovery_key`).
* A banner while the connection is lost; the app reconnects by itself and reloads what it shows.

The assistant in this demo is a **scripted stand-in** (`claudia_server.ScriptedEngine`): it understands a few
phrases (say `@ai help`) and says so when it does not understand. It edits through the same method table as everybody
else, so locks and roles apply to it. The real model replaces the engine (E3.6) without any change in the client.

Not in v0: formulas (typed text starting with `=` is kept as text), restoring checkpoints, objects and charts,
sliders, encryption of the file store, column resizing.

## Writing in composes

`./start.sh composes` serves texts (documents in `./.claudia/composes/documents`, because a directory holds one
app's documents). The text view lives in `TextWorkspace.vue` and `TextEditor.vue`; its state is `lib/text-session.ts`
(`TextSession`, next to the workbook's `Session`, both built on `lib/base-session.ts`) and `lib/blocks.ts` (pure:
the paragraphs, the events that change them, where a caret or zone goes when somebody else writes).

* **Paragraphs with named styles** (Body text, Title, Heading 1/2, Quote, Remark, Definition). You mark text by what
  it is for (D62); Enter after a heading starts body text. Every style is CSS held in the document (D73): all are
  based on Body text, so changing Body text changes them all, except where they set the property themselves. The page
  draws a paragraph from its computed CSS (`lib/style-css.ts`); the element only says what it is (heading, quote).
* **The style menu** (right-click, Shift+F10, or Format ▸ Look of this style…). *Paragraph style* lists the styles
  (you mark text by what it is for); *Look* shows the style's look as **Controls** (font, size, bold, italic,
  underline, strike-through, alignment, text and background colour) or as its **CSS**, one switch, remembered. The CSS
  view is the style's own declarations, checked by the server as you type (`check_css`, errors with their line) and
  applied with Ctrl+Enter. A change goes to *This paragraph only* (the default: it makes a new style that is named
  later, `Body text (changed)`, flagged *to name*) or to *Every use of “X”* (changes the style). A style still
  waiting for its name is yours, so the next change goes into it, and the menu invites a name once. *All styles…*
  lists styles with their use counts and renames them. Nothing outside the CSS allow-list of `claudia-core` can be
  written (no `url()`, `var()`, `calc()`); see `CSS_VERSION`.
* The menu is app-agnostic: `StyleMenu.vue`, `StyleSpec.vue`, `Popover.vue` and the pickers talk to a `StyleHost`
  (`lib/style-host.ts`; `lib/text-style-host.ts` is the text's) and `StyleEditor` holds the rules (where a change goes,
  the controls' edits). Cells and shapes bring a host of their own; the menu does not change.
* **Typing** is shown at once and sent when the word ends (a pause or any other action sends it too), so a word is a
  step in the history. Text appears in the document only when the server's events say so; the browser never edits the
  page itself. Everything goes through `replace_text` (a range, which may span paragraphs, replaced by text).
* **Colleagues**: their caret with their name and the ± 3 words around it (D11), which are locked for everybody else
  while they write there. Your own zone is held the same way.
* **Who wrote what** (View ▸ Show who wrote what): runs coloured by author; text that came from a suggestion is
  dotted and says whose it was.
* **The assistant suggests** in texts (D262: both modes suggest here for now). `@ai review this text` (or `check this
  paragraph`) makes suggestions; they are marked in the text, and clicking a mark opens it: what would change and why,
  with Accept and Reject (or Dismiss for a remark). The count in the bottom bar opens the first one. Accepting is an
  ordinary edit by the accepter. A suggestion whose text changed cannot be accepted any more.
* Flow and Page views, Save as Markdown (current text only).

Known gaps: bold/italic and lists, windowing of very long texts (the whole text is loaded), an exact page layout
(Page is a sheet with margins), input methods are minimal (the composed text is sent when composition ends), and each
word is one undo step (the kernel has no grouping yet).

## Build and run

The quick way (Linux, macOS: `./start.sh`, Windows: `start.cmd`) builds the web app when it is missing, starts the
server of all three apps and opens the browser. Each app's documents are kept in `./.claudia/documents/<app>`, each one
sealed (encrypted), and the server's certificate and settings in `./.claudia/state`; `--dir DIR` uses `DIR/` instead.
Folders of earlier layouts (`.claudia/<app>/`, `docs-<app>`, `demo-docs*`) are named at start so that they can be
deleted, never used (D437); a folder of plain files from the early demos needs `--plain-dir`.

Naming an app only chooses the page the browser opens (D433):

```bash
./start.sh                       # all three apps at http://127.0.0.1:8765/; or: uv run python scripts/start.py
./start.sh composes              # the same server; the browser opens ?app=composes
./start.sh creates               # the same server; the browser opens ?app=creates
./start.sh --ai                  # the AI user of computes and creates answers with the model in ai-models/ (OpenVINO)
./start.sh --dir ~/claudia-data --port 9000 --no-browser
./start.sh --rebuild             # build the web app again first
./start.sh --tls                 # encrypted; the browser warns once about the server's own certificate
```

By hand (needs Node.js 22 or newer for the build):

```bash
cd web && npm ci && npm run build             # writes web/.output/public (npm ci also installs ../layout's dependencies)
cd .. && uv run python -m claudia_server --no-tls --dir .claudia/documents \
    --state-dir .claudia/state --web web/.output/public
```

Open <http://localhost:8765>, create a document (the creator is its owner), then share it and join from a second
browser to see presence, locks and the assistant working.

## Tests

```bash
cd web && npm test           # vitest: protocol client, workbook and text sessions, text replica, selection, people
npm run coverage             # the same, with app/lib's coverage against its thresholds
npm run typecheck            # nuxt typecheck (vue-tsc over the generated projects)
npm run lint                 # ESLint
```

The browser scripts in `web/e2e/` drive real Chromium windows through Playwright (a dev dependency; fetch the
browser once with `npx playwright install chromium`). Build the app (`npm run build`). Until the web app chooses the app
by address (D431), each script talks to a server of one app: start one per app the old way (D433), on the ports the
scripts expect, as CI does:

```bash
port=8765
for model in claudia_computes.model:WorkbookModel claudia_composes:TextModel claudia_creates:SlideModel; do
  uv run python -m claudia_server --no-tls --port $port --model $model --web web/.output/public \
    --dir /tmp/claudia-e2e-$port --state-dir /tmp/claudia-e2e-state-$port &
  port=$((port + 1))
done
```

then:

```bash
URL=http://127.0.0.1:8765/ npm run e2e            # two people and the assistant in one table
URL=http://127.0.0.1:8765/ npm run e2e:pointing   # picking cells with the mouse while typing a formula
URL=http://127.0.0.1:8766/ npm run e2e:composes   # two people and the assistant in one text
URL=http://127.0.0.1:8766/ npm run e2e:styling    # the style menu, the colour roles and the CSS view
URL=http://127.0.0.1:8767/ npm run e2e:slides     # two people on one slide
npm run e2e:resilience       # starts its own server on 8766, restarts it, checks that both browsers come back
npm run e2e:recovery         # starts its own server on 8767: the recovery key, shown once, and a new one
npm run e2e:search           # starts its own server on 8768: Edit ▸ Search & replace, the marks, the builder, one undoable replace
npm run e2e:pivots           # starts its own server on 8769: Tools ▸ Pivot Table…, the field panel, value settings, SQL, delete and undo
npm run e2e:macos-shell      # the macOS client's window: its shell page and core in Chromium, the web app in the frame
npm run e2e:windows-shell    # the same, built for Windows
```

The scripts that start a server of their own need ports 8766, 8767, 8768 and 8769 free, so stop the three servers first. `e2e:macos-shell` needs the macOS and Windows client built for macOS
(`cd clients/neutralino && npm ci && npm run build:macos`) as well as the web app (`e2e:windows-shell` the same with `build:windows`; the two write
the same folders, so build right before each), starts a server of its own for each app and one on 8791
for `--server`, and fakes only Neutralino's client library; `CHROMIUM=/path/to/chrome` picks a browser binary other than Playwright's. CI runs all of them in its `e2e` job,
together with `tests/e2e` (the Python test that checks each server greets with its own app).

`npm run lint` runs ESLint (`eslint.config.mjs`: Nuxt's recommended rules without the stylistic ones; every rule
switched off or narrowed there says why), and `npm run coverage` runs the unit tests with `app/lib`'s coverage held to
the thresholds in `vitest.config.ts`.

`uv run python scripts/check_debt.py` runs the web checks too (skipped when npm or `web/node_modules` is missing, and
named in the summary line either way: a skip is never reported as clean). `--ci` turns an unlisted skip into a
failure; CI's Python job allows this one because the separate `web` job covers it with Node installed.

The gate also audits the lockfiles of `web/` and of every client with `npm audit` (`scripts/check_npm_audit.py`, SEC-08).
It needs no `node_modules`, only npm and the registry; an advisory of moderate severity or worse fails it (`--level high`
for a narrower look), development tools included. Fix one by updating the direct dependency that brings the package in,
or with an `overrides` entry in `package.json` where the dependent has no newer release. What cannot be fixed is
recorded in `pyproject.toml` under `[[tool.claudia.npm-audit-allow]]`, one entry per advisory with its reason; an entry
that nothing needs any more fails the audit. Where npm or the registry cannot be reached the check is skipped and says
so, and `--ci` fails on that skip.


## Presentations (creates)

The same web app opens presentations: it asks the server what kind of document it holds (`welcome.app`) and shows the
slide view for `creates`, the table for `computes`. Start a presentation server with
`./start.sh creates` (or `uv run python scripts/start.py creates`).

* One slide on screen, scaled to fit; **Slide 1, 2, …** along the bottom, **+** adds one.
* **Insert** (menu or tool bar): a text box, and every shape in the server's library (rectangle, circle and triangle
  are built in; `--shapes DIR` adds more, see {doc}`server`).
* Click selects an object and *holds* it: colleagues see your mark with your name and cannot change it until you select
  something else. Drag moves it, the handles resize it (a circle only from the corners: it stays round), a double click
  or Enter writes in it (Enter keeps the text, Shift+Enter starts a new line, Esc drops it), Delete removes it, the
  arrow keys nudge it (10 units, with Shift 1).
* The slide is drawn in screen pixels rather than scaled by CSS so that outlines keep their width; the lengths of a
  style (`font-size`, `stroke-width`, `letter-spacing`) are scaled in `lib/slide-style.ts`.
* What you do while the pointer is down is a preview on your screen; the change is sent when you let go, and the screen
  shows what the server then says (a refusal snaps the object back).
* `e2e/slides.cjs` (`npm run e2e:slides`) runs two people on one slide in two real browser windows.

Not in this first draft: text formatting beyond the two built-in styles, images, groups, copy and paste of objects,
reordering objects, slide order and slide thumbnails, and the assistant (the AI user does not answer in presentations
yet; the panel with history and chat is there).

## Printing (composes and creates)

**File ▸ Print…** (Ctrl+P) shows the pages in place of the document, laid out in the browser by `@claudia/layout`
(D901); Print… hands the very PDF the pages are drawn from to the browser's print dialog, Download PDF saves it, Esc
goes back. It is one component in both apps (`components/PrintPreview.vue`, D918): what it prints comes from a print
source (`lib/print/source.ts`, `textSource` and `slideSource`), and `lib/print/use-print.ts` gives each window its
Ctrl+P, its printing mode and the language a new document starts in. The bar is the same in both — paper,
orientation, margins, language, page numbers — and a presentation adds **Layout**: slides one to a page (on a
slide-sized page by default) or handouts of 2, 3 (with lines for notes), 4, 6 or 9 to a page (D917). How a document
prints is part of it, one step in its history for everybody; a viewer sees the pages but cannot change them.
`e2e/print.cjs` and `e2e/print-creates.cjs` (`npm run e2e:print`, `npm run e2e:print-creates`) drive both.

## Presenter mode (creates)

Every slide has **speaker notes** (Markdown, a field under the slide) and a **planned time** (the ⏱ chip beside it:
`2` is two minutes, `2:30`, `90s`, `1h`; the buttons 1, 2, 3, 5 and 10 min). Both are document content, one step in the
history, readable by a viewer and written by whoever may edit (D342, D343). The tab of each slide shows its time and
the bar below adds them up, with how many slides have none yet. View ▸ Speaker notes hides the field (a personal
setting, `lib/show-prefs.ts`).

**Present** (the apricot button, View ▸ Present from the first slide / from this slide) opens the show over the
workspace: **F5** from the first slide, **Shift+F5** from this one, and **Ctrl+Alt+P** / **Ctrl+Alt+Shift+H** where F5 is a
system key (a Mac, D344). It is read-only and local (D340) and runs on a frozen copy of the presentation (D341,
`lib/frozen.ts`): a colleague's edit changes nothing on the screen, and the presenter view says "Changes since you
started: N" with an **Update now** button. In the show: ← → Space PageUp PageDown Backspace go through the slides,
Home and End jump, a typed number and Enter go to that slide, **G** the overview, **B** a blank screen, **P** swaps
between the audience view and the presenter view (current and next slide, the notes formatted, elapsed time against the
planned total, the pace, this slide against its time, the clock), **F** toggles fullscreen, **Esc** steps back out one
layer and then ends. The window announces each slide to a screen reader and respects reduced motion. The rules are in
`lib/show.ts` (tested without a browser); `components/PresentShow.vue` draws them; `e2e/present.cjs`
(`npm run e2e:present`, `BROWSER=firefox` for Firefox) drives all of it. A second audience window on another screen is
not built yet (D345).

## Search & replace panel, movable dialogs, help topics

**Search & replace** (Edit ▸ Search & replace…, Ctrl+F; D282) is one component, `components/SearchPanel.vue`, for all three
apps; each app gives it a `SearchHost` (`lib/sheet-search-host.ts`, `lib/text-search-host.ts`, `lib/slide-search-host.ts`)
that says which kinds of text exist (`switches`), how far to look (`scopes`), how to name and go to a match, and which help
topic explains it (`helpTopic`). Its quick path is a find field, a **Look in** button, the scope list, two checkboxes and
the buttons **Replace with…** and **Build a pattern…**; the line above the matches reads "n matches" (D521). The two lines
of text are plain functions in `lib/search.ts`, so they are tested without a browser:

```ts
lookInSummary(kinds, t)               // "Everything (5)", "Text, Headings (2)", "3 of 5 kinds", "Nothing"
matchSummary(count, units, unit, t)   // "No matches", "One match", "12 matches", "12 matches in 5 cells"
```

**Moving** (D520). `components/Modal.vue` (every dialog) and the search panel have a title bar that is the handle:

* `lib/dragging.ts` is the pure part: `clampShift` keeps a box inside the window with a 48 px strip of its title bar
  reachable, `dragged` and `keyShift` say where a drag or Alt+arrows (20 px, Shift 100 px) take it, `startsDrag` says that a
  button or field in the bar does not start a drag, `takesTyping` that Alt+arrows are left to a text field.
* `lib/use-draggable.ts` is the wiring (pointer events on the window, one remembered offset per dialog title while the
  page is open, a re-fit when the window shrinks, `justDragged()` so the click that ends a drag does not close a dialog by
  its backdrop).
* The box applies its offset to its own insets through the CSS variables `--dx` and `--dy`. Do not turn that into a
  `transform`: it would make the box the containing block of the `position: fixed` popovers inside it.

A new dialog gets all of this by using `Modal.vue` with a `title`; nothing else is needed. A box that is not a `Modal` calls
`useDraggable(ref, id)`, puts `@pointerdown="start"` on its title bar and `@keydown="key"` on itself, and reads `offset`.

**Help topics** (D522). The Help tab shows a topic's Markdown, not its source: `lib/help-markdown.ts` joins the line breaks
inside a paragraph (the files are written in lines of about 120 characters) and `lib/notes-markdown.ts`, the reader of the
speaker notes (D347), turns the text into lines of spans, which `components/NotesText.vue` (with `flow`) draws. It is
never HTML. A host opens its own topic with `frame.openHelp('how-to', host.helpTopic)`; an unknown id shows the how-to
list. A topic is a file of the app's package (`claudia_<app>/help/<name>.md` and `<name>.de.md`; the German one carries
the `source-hash` of the English file, see `claudia_server/help.py`).

Tests: `npm test` runs `dragging.test.ts`, `help-markdown.test.ts`, `search-panel-wording.test.ts` and the hosts'
tests; `npm run e2e:search` drives the panel against a real server.
