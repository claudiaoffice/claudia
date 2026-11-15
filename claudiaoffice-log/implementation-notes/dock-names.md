# The dock: names of things (D550) and the replay backend (D551)

First slice of the dock work (branch `dock`): scrubbing the history and tags in the chat (D551) both need things that
have names. The mock-ups are `notes/mockups/dock-01-…` to `dock-06-…`; they draw the dock light, the real dock is
Ink-dark, which the built screens will follow.

## What was built

* **The rule** (`claudia_core/names.py`): `clean_name`, `name_key` (cleaned and `casefold`ed), `name_problem`
  (1 to 60 characters, no control characters), `free_name(label, taken)`.
* **Kernel** (`claudia_core/objects.py`): `ObjectBody.name`; `ObjectModel.named_things()` is the one list of
  `(kind, id, name)`, `unnamed_things()` the one list of what has none; `check_thing_name` (tidy and free) and
  `check_name_free` (free only; for commands that may be in an old log); `RenameThing` with an exact inverse, refused
  by `shifted_by` when the thing was renamed, removed or made again since; `ThingRenamed`.
* **Apps override the lists.** Creates adds its slides (state schema 11, `slide_names`); computes adds sheets and chart
  tabs. Composes has objects only. `set_thing_name` is where a thing keeps its name; computes refuses a sheet.
* **Documents are forever.** `AddObject` schema 3 → 4 (upcaster adds `name: ""`); `AddSheet` and `AddChart` schema
  1 → 2: the upcaster sets `legacy_names`, so those entries keep the old rule, and so do the inverses of a removal that
  had a clash already. Only new commands meet the shared rule.
* **Server** (`claudia_server/thing_names.py`): `default_name(ctx, kind)` (the first free "<label> <n>", label from
  `msg`, said in the connection's language), `rename_thing`, `name_unnamed` (one `Batch` step). Registered in the three
  apps (composes through `_people_only`); `slides` returns each slide's `name`. The AI-facing `add_sheet` and
  `add_chart` keep the name they are given.

## The replay backend

* `Document.peek_revision(rev) -> Look` (`claudia_core/document.py`): `materialize(rev)` for the state, the entry, and
  `focus`: the command's `regions()` read against the state before the step and then against the state after it, each
  place once (a removed thing is found before, a new one after; a command that cannot place itself in one of the two
  adds nothing from it). Nothing live is touched.
* `peek_revision` over the wire (`claudia_server/protocol.py`, all three apps): `{revision, entry, focus, app,
  state_schema, state}`; `entry` is exactly what `log` gives for the step (`_entry_view`); `state: false` leaves the
  state out for a client that only wants the place. Tests: `test_peek_revision.py` (core), `test_server_peek_revision.py`.
* `as_of(revision, method, params)` (`claudia_server/replay.py`, registered in all three apps): runs one of the view
  reads in `VIEW_READS` against a `PastDocument` (the live document with the step's model and revision), so no app needs
  a second reader for the past. Anything not in the list is `forbidden`, a revision the log lacks is `command_error`.
  Up to six rebuilt states are kept for 30 s (`state_at`). Tests: `test_server_as_of.py`.

## The replay in the web client

* `lib/replay.ts`: the playhead's logic (`timeline`, `step`, `WheelStepper`, `keyStep`) and `PastLink`, which wraps the
  session's link while replaying: reads go as `as_of`, the conversation stays live (`LIVE_REQUESTS`), the rest is
  refused as `forbidden`. `VIEW_READS` there must match the server's (apps' `loadApp` only use listed reads).
* `BaseSession` (`state.replay`): `startReplay`, `replayStep`, `replayGo`, `setReplayFilter`, `setReplayFollow`,
  `endReplay`. Stepping is latest-wins: while a step loads, further steps only move `replayWanted`. App events are
  ignored while replaying, `command` counts as `newer`, and any `reload()` ends the replay first. An app says how to
  follow a step in `followReplay(focus)` (slides and sheets switch the active one; the text and the grids scroll from
  `state.replay.focus`).
* Views are read-only while replaying through `lookOnly(state)` / `roleNow(state)`, which replaced the scattered
  `role === 'viewer'` checks.
* `SidePanel.vue`: Replay button, wheel (`WheelStepper`; wheeling up in the present starts, Ctrl+wheel scrolls), keys
  (`keyStep`), filter chips, Follow, position and the newer count, a polite live announcement of each step; the playhead
  row has a bar and `aria-current="step"`, so it is not only a colour. `Workspace.vue`/`TextWorkspace.vue` watch
  `state.replay.focus` to scroll. `view.replay` is in the shared view block of the manifest (Ctrl+Alt+Z), from which
  the web keys and the Windows and macOS menus are generated.
* Tests: `replay.test.ts`, `replay-session.test.ts`.

## The tags (E5.20)

* `lib/tags.ts` (pure): `encodeTag`/`splitTags` (`[#name](thing:id)`, `[ ] \` escaped), `hashAt` (an open `#…` before
  the caret that starts a word), `matches` (starts-with before contains, by name key), `withTag`.
* `BaseSession`: `taggableThings()`, `nameUnnamed()`, `nameOf(id)` (current name: `renamed` from `thing_renamed`, else
  the replica), `isGone(id)`, `goToThing(id)` (`state.pointed {id, container, from}`; marks for 3 s), `goBack()`,
  `thingToReference(id)`. Each app says what it knows by overriding `things()`, `inView()`, `containerOf()`,
  `currentContainer()`, `showContainer()` (creates: slides and objects; computes: sheets, chart tabs, objects;
  composes keeps no replica of objects, so it asks `objects` when a tag needs them).
* A tag to something gone: `thing_last_seen` (server, `replay.py`) asks `Document.last_seen`, one forward replay of the
  line on a scratch model; the session then starts or moves a replay there.
* Views: `lib/pointed.ts` (`usePointed`) outlines the thing (class `pointed`, an outline plus a tint, not only a colour;
  the view jumps instead of gliding when the system asks for reduced motion). `Workspace.vue` also switches to a chart's
  tab; `TextEditor.vue` scrolls to the paragraph.
* Shortcuts: Ctrl+Alt+Z replay, Ctrl+Alt+X reference (D551 as first written had H and R, which were taken).

## Why

* One namespace, because "figure 1" in the chat has to mean one thing; ids stay unrelated to names, so a rename never
  breaks a tag, an undo or a formula.
* `legacy_names` rather than a migration: an old document must replay unchanged, and a migration cannot decide which of
  a sheet and a chart tab called "Sales" should be renamed.
* Names default to words, not ids, because a person reads them.

## Numbers

Core 0.24.0, creates 0.12.0, computes 0.8.0, composes 0.9.0, server unreleased (API snapshots regenerated). New
tests: `test_core_thing_names.py`, `test_creates_thing_names.py`, `test_computes_thing_names.py`,
`test_server_thing_names.py`. Decisions D550, D551; stories E1.13, E6.24, E5.19, E5.20.

## Not built

The rename field in the clients (properties, F2 on a tab or slide); names read from and written to pptx, odp, docx and
xlsx files (take them from the file, suffix duplicates, write them back); names in the assistant's view of a document;
renaming a sheet (E6.24); composes' own object list in the dock. Both dock interfaces (E5.19, E5.20) are next; the
the rename field in the clients and file import/export of names are next.
