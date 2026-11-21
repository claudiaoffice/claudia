# Implementation notes: one asset store, one web document session, the first glossary renames

Written 2026-11-21, branch `architecture-improvements`. The review that led here chose two deepenings out of seven
candidates; the decisions are D1430 (names), D1431 (asset store) and D1432 (web session, CODE-75). This file keeps what
the code does not say.

## The asset store (D1431)

- **`claudia_core.assets` was taken.** It is the image module (`ImageAsset`, `decode_image`). The store lives in
  `asset_store.py`, its commands in `asset_commands.py`; `objects.py` imports the store, the commands import `objects.py`,
  so `AddObject.shifted_by` recognises a `ForgetAsset` by its kind string (`"core.ForgetAsset"`), as the table commands
  already do, instead of importing it.
- **A shape is now read back from plain data when its step runs.** `DefineShape` carried a `ShapeDefinition` and never
  checked its path again; `DefineAsset("shape", data)` reads it with `ShapeDefinition.from_data`, which refuses an outline
  the shape format does not allow. One test had a path with `H` and `V` in it and was given absolute `L` instead.
- **Who uses an image** includes the containers whose picture it is (`ObjectModel.users_of`). The render desk's
  `_held_elsewhere` asks for users other than the container it is redrawing, or it would never let go of an old picture.
- **The stored state** of each app is `**self.assets_to_data()`: every kind of asset, under the keys it always had
  (`images`, `shapes`, `diagrams`, `renderings`, `tables`). A text and a slide now also store an empty `diagrams` list,
  a slide and a workbook an empty `tables` list; `restore_objects(objects, state)` reads whatever kinds a stored state has.
- **Tables** share the store (`model.tables.define/known/replace/forget`) and keep their own commands and their own
  `TablesChanged` event; `DefineAsset("table", …)` is refused, so there is one way to define a table.
- The **wire did not change**: `AssetsChanged.to_data()` is `{type: "image"|"shape"|"diagram"|"rendering", id, asset|definition}`.

## The web document session (D1432)

- `BaseSession.write(method, params)` is the door for every change; `run(job)` is what composes overrides (its old
  `act()`), so a change waits for the words typed before it. **Never call `write` inside `run`**: the composes queue is
  one chain, and a job that waits for a job queued behind it never ends. The few composes flows that send several
  requests in one job (`setStyle`, `deviateStyle`, lists, contents) keep `refused()` + `run()` + `attempt()`.
- composes' own `write(from, to, text)` (typing) is `replaceText` now.
- The shared reducer runs before `onAppEvent` and, like it, not while looking at the past or at a preview. An app adds
  what is its own with `objectsChanged(event)` and `stylesChanged()` (computes: the use counts; composes: a selection
  that went; creates: a slide's object count and a selection that went).
- Styles are kept by id in all three apps. composes' helpers that want a list (`headingLevel`, `toMarkdown`, …) are given
  `Object.values(state.styles)`, which keeps the server's order.
- The slide session's `rotate`, `describe`, `remove` are `rotateObject`, `describeObject`, `removeObject`, as in the
  other two.

## The glossary renames done so far (E1.18, D1430)

Done: `Entry` → `Step`, `history.Step` → `UndoUnit`, the assistant's `Step` → `AiTurn`, `Line` → `BranchInfo`,
`lines()`/`peek_line` → `branches()`/`peek_branch`, `CommandLog.line` → `steps_of`; on the wire `branches`, `peek_branch`,
`propose_switch(branch)` and `branch`/`branches` in the welcome, in the answers of `ping`, `snapshot` and `peek_branch`
and in an open restore proposal; two server messages ("switching branches", "no branch called"); the web's log type
`Step`; in the side panel "Branches" ("Zweige").

Done since (2026-11-21, second session; the names around each slice were agreed with the owner first, D1433):

- **Holder and object layer** (`91c3d106`): `Anchor.holder`, `holders()`, `open_holder`/`close_holder`,
  `max_objects_per_holder`, `objects_change_holder`, `MAX_OBJECTS_PER_HOLDER`; on the wire and stored, an anchor, an
  `objects` region and the `objects` event say `holder`. Web: `TextObjectLayer.vue`, `lib/text-object-layer.ts`,
  `holderOf`/`currentHolder`/`showHolder`, the page's `data-testid` `object-layer` and `object-layer-behind`. The layout
  library's anchors follow.
- **Container** (`e9e4c4b3`): see D1433. The help topic `render.configure-tools` says container (en, de; the German
  file's `source-hash` follows the English one).
- **Paragraph** (`55c13243` Python and wire, `dc4236e0` web and layout): see D1433.

Waiting: **chart** (the owner wants to think about it more, D1433). Not done yet, in this order: proposal
(`Suggestion`…, `WhatIfProposal`, AI mode `propose`), ai (`assistant`), the UI strings of E1.18 (suggest, tag, line in
messages), and the package `claudia-document-file`. Each needs the owner's list first.

How the slices were done, for the next ones: a script with exact patterns, limited to the packages where the word has the
meaning, with a guard for lines in another sense; then a check, per function, that no two names became one (Python:
`ast`; TypeScript: the compiler's AST over the original files), the full `git diff` read, and a check that every request
the web sends with a literal payload names only parameters the server takes. The catalogue extraction caught two cell
"blocks" of computes the web rename had taken for paragraphs: rename a word in UI strings only with the strings in view.

## Assumptions

- Stored names (also the legacy pointer `container` of old object bodies, which the old-body reader matches against the
  kind) are renamed without readers for documents from before (E1.18).
- `insertFrame` takes a `FramedKind` (`Exclude<ObjectKind, 'diagram' | 'table'>`), because spelling out four kinds is
  refused by `tests/test_object_kinds_agree.py` now that `container` is one of them.
- `LookHolder` (`text-object-look.ts`) and the converters' local `holder` of an XML element keep their names: they do not
  name the glossary's holder, but a reader may stumble on them.

- The stored names of commands and objects change without a way to read documents from before (E1.18, pre-release).
- `name_thing` (naming a paragraph when it is first pointed at in the chat) still goes through `attempt`, not `write`:
  a viewer may write in the chat, and the server decides whether she may name the paragraph.

## What could not be run

- Second session: the whole gate ran green after each commit, this time with `web lint`, `web tests`, `web types`,
  `layout types`, `layout tests` and the Linux client's tests too; only `e2e greeting` was skipped (the web app is not
  built in the workspace). The journey tests (`web/e2e`, `tests/e2e`) were changed with the names but not run.

- **The end-to-end tests and "use it before delivery".** The browsers Playwright needs cannot be downloaded in the
  workspace this was built in (`cdn.playwright.dev` is not reachable). What did run: the whole Python gate
  (`scripts/check_debt.py`: lint, types, dead code, i18n, tests, coverage, docs, perf, the Linux client's tests), the web
  unit tests (1957), web lint and web types. The layout checks (`layout types`, `layout tests`) need the layout
  package's own `npm ci`, which was not run; nothing in `layout/` changed.
- CI runs on `main` and on pull requests only; it has not run on this branch.
