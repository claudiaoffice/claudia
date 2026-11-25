# Claudia — bug tracker: open items

The tracker is two files: this one, the *Open* table and the sections of the open items, and `bugtracker-fixed.md`,
the *Fixed* table and the record of every round (the owner split them on 2026-11-25; until then both were
`bugtracker.md`). When an item is fixed, its row and its section move to `bugtracker-fixed.md`, under the round that
fixed it. Stories are in `Projects/claudia-office/_tasks/` (E-numbers), decisions in `decision-log/` (D-numbers).

## How to add a bug

Tell the QA role in chat: *title, what you saw, where*. It is entered in this file with the next ID (the highest number
of its category in both files, and on every branch, plus one), a category, a proposed priority and a status. Every fix
follows `CONTRIBUTING.md` rule 1: **the bug first gets a test that fails for the right reason.** Where an item says
"Acceptance", that is the test to write first.

Priorities: **P1** before the product is shown outside the team or runs on any machine other than a trusted laptop.
**P2** before the first release, or before the story it belongs to is called done. **P3** backlog.

Status: `open` · `needs decision` · `in progress` · `fixed` · `wontfix`.
Dates: a new row gets its **Opened** date; a row that is fixed moves from *Open* to *Fixed* and gets its **Fixed**
date (the day the fix reached `main`, or the branch it is on, said in the status).
Evidence labels: **measured** (run against the real code), **read** (from reading code, not run), **documented** (a
statement in the docs or on the website).

## Index

The index is the status of record; a section below keeps the status of the round it was written in unless it says it was
re-checked. **Opened** and **Fixed** are filled from 2026-11-20 on: for older items only where the status already gave
the date.

### Open (63)

By priority (P1, P2, P3, then items that wait for a decision without one), then by ID.

| ID | Pri | Category | Title | Status | Opened | Fixed |
|---|---|---|---|---|---|---|
| SEC-19 | P2 | Security / Perf | Imports run on the worker pool with no memory cap; `check_package` bounds the input, not the parsed model | **new, open** |  |  |
| SEC-22 | P2 | Security | Who wrote which stretch (`runs`, E9.10) is part of the content state, so a viewer still receives it: in the `blocks` method, in `text` events, in the snapshot and in her own sealed file, although D1261 says no data should be behind "show who wrote what" for a viewer | **new, open**, needs the owner's decision (mask it live and in the viewer's file, or accept it as content) |  |  |
| SEC-24 | P2 | Security / privacy | An owner's export writes every chat message into the file, also the private ones between other people that she cannot read in the document | **new, open** (read) | 2026-11-25 |  |
| SEC-25 | P2 | Security | An editor can send a whole `Import` command through `apply` and so replace the document (or write a forged "History of the original") | **new, open** (read) | 2026-11-25 |  |
| PERF-02 | P2 | Performance | Journal `fsync` on the event loop for every edit | verified open (2026-11-12; see CODE-13) |  |  |
| PERF-10 | P2 | Performance | What-if outcomes are recalculated on the event loop: 9 s per edit in a 1,000-cell model | **new, open** |  |  |
| UX-22 | P2 | UX | The history speaks three dialects: one per app | **new, open** |  |  |
| UX-42 | P2 | UX / all | A document cannot be renamed: its name is sealed into the file, which the uid was meant to avoid | **decided, open** (D536, E5.21) |  |  |
| UX-51 | P2 | UX / composes | The words go round the unturned frame of a turned object, not its bounding box (D1226 decides the box); turning is on screen in composes since D1232 | **new, open** (read) |  |  |
| UX-68 | P2 | UX / computes | A sheet or a chart tab (after E6.31: a slide) cannot be deleted: nothing in the menus or the tab strip reaches `RemoveSheet` or `remove_chart` | **new, open** (read; size 2) | 2026-11-22 |  |
| UX-69 | P2 | UX / all apps | A viewer is not told she can only look: greyed entries, hidden controls and object gestures are silent (only Delete on a sheet's object says so) | open (scenario `@pending:UX-69`) | 2026-11-22 |  |
| UX-71 | P2 | UX / computes | Text on a workbook's slide is drawn in the workbook's Body text (13 px), tiny on a 1600-unit slide | **needs decision** (measured; size 2) | 2026-11-22 |  |
| UX-91 | P2 | UX / composes / Firefox | In Firefox the down arrow from the paragraph above a new table does not put the caret in its first box (Chromium does) | **new, open** (measured on CI) | 2026-11-25 |  |
| UX-93 | P2 | UX / a11y | The font banner ("This document uses fonts this server does not have …") is dark text on a dark ground, about 1.1:1 (BITV 1.4.3 asks 4.5:1) | **new, open** (measured) | 2026-11-25 |  |
| CODE-31 | P2 | Code / i18n | The history speaks English to everybody: command labels and summaries are not translated | **new, open** |  |  |
| CODE-99 | P2 | Code / desktop clients | A person's apps use any Claudia server on port 8765 of the computer as their own, also another person's or a service's: with two people logged in, the second one's documents are saved in the first one's home folder | **in review on `mac-installer`** (E8.5 part 1, D1620, D1621; waits for the owner's acceptance) | 2026-11-25 |  |
| CODE-100 | P2 | Code / desktop clients | Next to a service of another version, the apps refuse to start and say it stops after ten minutes, which a service never does | **in review on `mac-installer`** (E8.5 part 1, D1620, D1621; waits for the owner's acceptance) | 2026-11-25 |  |
| PROC-15 | P2 | Process | The tracker and the backlog lag the code: fixed items still "open", 64 stories at a placeholder 50 % | partly fixed 2026-11-25 (batch 1: the index guard); the backlog's placeholder 50 % stays open |  |  |
| PROC-30 | P2 | Process / desktop clients | The Neutralino (Windows, macOS) tests and the GTK client were not run for `object-interaction`: the generated menus were rebuilt and the manifest unit tests pass, nothing more | **new, open** |  |  |
| UX-64 | P2 | UX / all apps | Dark mode: a part of the sidebar (History & Chat / Help) is not readable or has too little contrast; the exact symptom was not written down when it was seen (see entry) | **needs decision** (symptom to be re-stated; size 2) | 2026-11-22 |  |
| SEC-09 | P3 | Security | User names can be confusable (homoglyphs) | open (unverified) |  |  |
| SEC-16 | P3 | Security | The LaTeX program setting accepts any executable on the server | partly fixed 2026-11-25 (batch 1, D2002): showing the accepted program's answer on the settings page stays open |  |  |
| PERF-06 | P3 | Performance | Threshold packing blocks the event loop (rewriting the whole zip is accepted up to ~50 MB, D1269) | verified open; narrowed 2026-11-22: the rewrite itself is accepted (D1269) |  |  |
| PERF-07 | P3 | Performance | Structure edits recalculate the whole workbook (~12 s at 100k formulas) | verified open |  |  |
| PERF-08 | P3 | Performance | The first chart downloads all of Plotly (4.6 MB) for a bar chart | **new, open** |  |  |
| UX-08 | P3 | UX | Open and Create sit side by side; a typo cannot be told from a wrong password | open |  |  |
| UX-23 | P3 | UX | Panel layout and undo placement differ between the three apps | partly fixed 2026-11-12 (the suggestion list is gone from above the tabs) |  |  |
| UX-34 | P3 | UX / AI | In computes and creates the AI refuses every change by default (suggest is the default, proposals do not exist) | deferred (owner, 2026-11-13: the AI is not fully built yet) |  |  |
| UX-43 | P3 | UX / creates | A text box whose words become a container is two undo steps and loses its name (a tag to it breaks) | **new, open** |  |  |
| UX-45 | P3 | UX / composes | Resizing an object from its top or left handle is two history entries, not one (`resize_object` takes no offset in a text) | **new, open** |  |  |
| UX-46 | P3 | UX / computes, composes | Edit ▸ Select Next Object (D1063, D1222) is not built: computes reaches an object only by Ctrl+Alt+PageDown/PageUp, which has no menu entry | **new, open** |  |  |
| UX-47 | P3 | UX / computes, composes | Delete on a selected object or table works, but has no menu entry and no key in the key table in composes and computes (the hint "Del" is typed into the context menu) | **new, open** |  |  |
| UX-48 | P3 | UX / all | The object clipboard (D1229) copies pictures only: no box or shape, and nothing from another program can be pasted as a picture | **new, open** |  |  |
| UX-49 | P3 | UX / composes | A table has no width handle: its width is set only in Table options… (D1224 says it can be scaled in width) | **new, open** |  |  |
| UX-50 | P3 | UX / composes | Composes tables have no row and column headers, so *Height / width…* and *Insert / delete ▸* on a header (workbook rows 18, 19) cannot be offered | **new, open** |  |  |
| UX-52 | P3 | UX / computes | A dropped object snaps to the nearest cell border on release, so its free position is lost (D1230, by design) | **needs decision** |  |  |
| UX-53 | P3 | UX / computes | An object keeps its pixel size when rows or columns are inserted or resized, so it no longer covers the cells it covered (E6.17, D1230) | **new, open** |  |  |
| UX-60 | P3 | UX / composes | Dragging an object to another paragraph is "Moved an object" in the history; the mock names the object and the paragraph | **new, open** (divergence from the mock of D1352; size 3) | 2026-11-20 |  |
| UX-65 | P3 | UX / composes | Search & replace panel, find-only state: the results list overflows its container and the "text" badge of a result is clipped at the panel edge | **new, open** (`web/app/components/SearchPanel.vue`; **measured** in the running app; size 3) | 2026-11-22 |  |
| CODE-03 | P3 | Code | README is out of date | open (not re-checked) |  |  |
| CODE-04 | P3 | Code | Untyped functions escape the type check | verified open |  |  |
| CODE-06 | P3 | Code | `--max-connections` is per document, not per server | open |  |  |
| CODE-19 | P3 | Code | A debugging scan of the garbage collector and a 10 s sleep loop left in the journal | **new, open** |  |  |
| CODE-21 | P3 | Code | `claudia_server/computes.py` holds every computes method (1,228 lines) | open; search split out 2026-11-13; 1,121 lines at `7994b00` (see CODE-27, CODE-29) |  |  |
| CODE-28 | P3 | Code / Arch | An app's server wiring is spread over five tables in `apps.py` | **new, open** |  |  |
| CODE-29 | P3 | Code / Arch | `claudia_server` is flat: app glue next to infrastructure | **new, open** |  |  |
| CODE-30 | P3 | Code / server | Parameters are validated twice, and a handler's bug answers `command_error` | **new, open** |  |  |
| CODE-32 | P3 | Code / clients | The menu's one source lives inside the Linux shell, and the web menus are a second copy | **new, open** |  |  |
| CODE-38 | P3 | Code / naming | computes kept the generic names (`Session`, `Workspace.vue`, `standin.py`) | **new, open** |  |  |
| CODE-39 | P3 | Code / web | `OpenDialog.vue` does five jobs in 1,615 lines | **new, open** |  |  |
| CODE-41 | P3 | Code / Arch | Import cycles in computes are worked around with 29 function-level imports | **new, open** |  |  |
| CODE-47 | P3 | Code / Import | Words of a docx with a font of their own are a `formatting` loss | open, **postponed** by the owner (2026-11-25; D2004 decided, not built) |  |  |
| CODE-53 | P3 | Code / web | The failure text of a rendered container is clipped in a small frame and cannot be read in full | open |  |  |
| CODE-62 | P3 | Code / Linux client | A window that revives the shared server while the old one still holds the port starts it on a random port, not the remembered one | **new, open** |  |  |
| CODE-63 | P3 | Code / composes | The Format ▸ Styles menu lists composes' built-in `contents-title` and `contents-1` to `contents-9` as "custom" styles | **new, open** (read) |  |  |
| CODE-68 | P3 | computes | Computes cannot make a text box or a shape, though a model can hold one (a file from another app) and an export reports it as `object` | **new, open** |  |  |
| CODE-74 | P3 | Code | `export_content` still answers `{format: "claudia-export 1", ...}`, a JSON that is neither the zip of D1270 nor documented anywhere; it is recorded as an export and the panel says "exported as claudia-export 1"; no window calls it | **new, open** (size 3; remove it or make it the zip) |  |  |
| UX-92 | P3 | UX / i18n | History & Chat says "undo" and "redo" in English before a step, and the "History of the original" copies it | **new, open** (read) | 2026-11-25 |  |
| CODE-101 | P3 | Code / Import | A pptx placeholder's inherited size and alignment (a title's 44 pt, centred) are neither read nor reported | **new, open** (read) | 2026-11-25 |  |
| CODE-102 | P3 | Code / Import | A pptx box with several bulleted paragraphs comes in with one bullet (one paragraph per box), and no loss says so | **new, open** (measured) | 2026-11-25 |  |
| CODE-103 | P3 | computes I/O | The ods chart patch: a chart in a cell that is moved and described in one export makes overlapping edits, so the kept file is written anew | **new, open** (read) | 2026-11-25 |  |
| CODE-104 | P3 | computes I/O | The pictures of an xlsx that LibreOffice wrote are not read in, nor the turned ones of such an ods | **new, open** (measured) | 2026-11-25 |  |
| CODE-105 | P3 | composes I/O | docx: a paragraph mark's own run properties count as a `formatting` loss, though nothing is lost | **new, open** (measured) | 2026-11-25 |  |

## Security

### SEC-09 · User names can be confusable · P3 · unverified
**Evidence (read).** `claudia_container.crypto._normalise_name` uses NFKC and `casefold`, which does not fold Cyrillic
`а` to Latin `a`. Only an owner adds users, so the risk is an owner impersonating a colleague in the history.
**Fix.** Reject mixed-script names, or mark two confusable names in one document. Verify with a two-user test first.

### SEC-16 · The LaTeX program setting accepts any executable · P3 · partly fixed
**Evidence (read).** `PUT /api/admin/settings/typeset` stores any path; `resolve_program` accepts any runnable file.
An administrator is trusted, but with SEC-12 that is anyone, and even without it a stolen admin session becomes
"run this binary on every formula". **Fix.** Accept the setting only after the program answers `--version` with an
XeTeX / pdftocairo banner (in the sandbox), and show what it answered on the settings page.

## Performance

### PERF-02 · Journal `fsync` on the event loop for every edit · P2 · verified open
**Evidence (read, `54d1245`).** `claudia_container/journal.py` `append` does `flush()` then `os.fsync()`
synchronously (lines 210–211); `filestore.py` `_write` does the same for the plain store. The call path is
`_Live.run` → `connection.handle` (synchronous) → `methods.dispatch` → `document.execute` → store append. So every
keystroke-sized edit fsyncs on the event loop and stalls every document the server holds.
**Fix.** The group commit named in the E2 design (D76 of that document, renumbered D106 here): a writer task off the
loop, several records per fsync, the request acknowledged after its batch is synced. Measure first on a spinning disk
and on a network volume.
**Acceptance.** With a store whose `append` sleeps 50 ms, `ping` latency of other users stays under 20 ms.

### PERF-06 · Threshold packing blocks the event loop · P3 · verified open (narrowed 2026-11-22)
**Narrowed 2026-11-22 (E2.1 closed).** Rewriting the whole zip is accepted up to about 50 MB (D1269); above that,
appending is the trigger for a story. **What stays open:** `_after_change` → `_pack` in `claudia_server/sealed.py` packs
on the event loop every 500 changes, so every other document on the server waits while a large file is rewritten. The
way out is a worker thread behind the document's lock, as D1282 describes for renewal.
**Evidence (documented, E2 slice 3 notes).** Packing writes the whole zip again every 500 changes and at release.
Release runs in a thread; threshold packing does not. Fine up to some tens of megabytes; larger documents need
appending or a split.

### PERF-07 · Structure edits recalculate the whole workbook · P3 · verified open
**Evidence (documented, formula notes).** Inserting a row in a workbook of 100k formulas takes about 12 s: every
formula is rewritten and recalculated. Ordinary edits are incremental and fast (~0.25 ms in a 50k-row workbook).
**Fix.** Rewrite only formulas that refer to the edited sheet; move cells without recompiling.

---

### PERF-08 · The first chart downloads all of Plotly · P3 · new, open
**Evidence (measured).** `ChartView.vue` lazy-loads `plotly.js-dist-min` (good), but that is the full bundle: a 4.6 MB
chunk (`web/.output/public/_nuxt/`), most of it map and 3-D code, for one bar chart. It also carries tile-server URLs
(only used by map traces, never fetched today). **Fix.** A custom Plotly bundle with `bar` (and the next planned
types) via `plotly.js/lib/core` + `plotly.js/lib/bar`, about 1 MB. **Acceptance.** The chart chunk ≤ 1.2 MB, guarded by
a size check in the web job.

## UX and UI

### UX-08 · Open and Create sit side by side · P3 · open
A mistyped document name on *Open* gives "the name or password is not right (or there is no such document)", and one
click on *Create document* then makes the person owner of a new empty document.
**Fix.** While the server lists documents, say when the typed name is not in the list; mark the default button by
context; make placeholders visibly lighter than entered text.

### UX-22 · The history speaks three dialects · P2 · new, open
**Evidence (measured, the three apps side by side).** computes: `ann A1 = Item`, `add sheet Sheet1` (terse, formula
style); composes: `typed "…"`, `new paragraph`, `style title`, `changed the style heading-1…` (lower case, ids instead
of names); creates: `Added a text box`, `Wrote Hello slide`, but `Add shape` (capitalised, past tense and imperative
mixed). The panel tab says "History & Chat", the header button "History & chat". **Fix.** One rule in the design
system (`notes/design-system.md`): past tense, lower case, the thing's *name* not its id, the value last; e.g.
`added a text box`, `added a circle`, `set A1 to Item`, `changed the style Heading 1`. The label strings live in one
place per app (`describe` of each command), so this is a wording pass plus a test that every command kind has a
description in that form. **Acceptance.** A test per app that walks every command kind's description.

### UX-23 · Panel layout and undo placement differ between the apps · P3 · new, open
**Evidence (screenshots).** In composes the suggestions sit above the History & Chat / Help tabs, so the tabs move
to the middle of the panel; in computes and creates they are at the top. Undo/redo: in the formula bar on the left
(computes), at the right end of the insert bar (creates, with Delete), absent from the bar in composes. The decided
History filter row (All / Conversation / Changes) is not built yet. **Fix.** Tabs always at the top; composes'
suggestions become a section inside "History & Chat" (or a third tab only in composes, by decision); undo/redo in the
same place in all three bars, mock-up first (`notes/mockups/`).

## Process and code

### CODE-03 · README is out of date · P3 · open
Not re-checked in this round.

### CODE-04 · Untyped functions escape the type check · P3 · verified open
**Evidence (read).** `pyproject.toml` sets `check_untyped_defs = true` but not `disallow_untyped_defs`, so a function
with no annotations is not checked against its signature — for example `SinglePageApp.get_response(self, path, scope)`
and `Gateway._hello` in `app.py`.
**Fix.** Turn on `disallow_untyped_defs` for `claudia_core` first (nearly typed already), then package by package with
per-module overrides.

### CODE-06 · `--max-connections` is per document, not per server · P3 · open
Rename to `--max-connections-per-document`, document it, and keep the server-wide caps from SEC-02 separate.

### PROC-15 · The tracker and the backlog lag the code · P2 · partly fixed
**Evidence.** In this file PERF-01, PERF-05, UX-01, UX-03 and UX-05 were "verified open" although fixed in the tree
(corrected above). In the backlog, E7.7 is `todo`, 0 % with a "Built 2026-11-11" paragraph; 64 of 90 stories that are
`in-progress` sit at exactly 50 %, which the README calls "an estimate from the code, not from hope" — 50 is a
placeholder. **Fix.** A branch that fixes a tracked item changes its row in the same commit (CONTRIBUTING rule);
`test_backlog.py` could refuse `progress: 50` on a story without a status-evidence paragraph.

## Round of 2026-11-13 at `cfa2d91`

### PERF-10 · What-if outcomes are recalculated on the event loop · P2 · new, open
**Evidence (measured).** Three inputs with 30 alternatives each and 1,000 formulas reading them: every edit of an input
*or of any of the 1,000 dependent cells* takes 9.0–9.5 s (`outcomes.py`: 27,000 combinations, sampled to 2,000 ×
1,000 cells, `MAX_WORK = 2_000_000`). An edit elsewhere costs 1 ms. The calculation is synchronous inside the command, so
the server answers nobody for those seconds.
**Fix.** Apply the edit and answer at once with the first alternatives' values; compute the summaries in the worker
pool (CODE-13) and send them as their own event (`outcomes` with the revision they belong to; a newer revision cancels an
older run). Then lower `MAX_WORK` for the synchronous path to what fits in ~50 ms, or drop it. **Test:** a server test
with the model above that an edit is answered in < 200 ms and the outcomes event follows.

### UX-34 · In computes and creates the AI refuses every change by default · P3 · deferred
**Evidence (read and measured).** D262 makes *suggest* the default in all three apps and says proposals (D263) must come
before the AI writes anything in computes or creates. Proposals exist only in composes (`SUGGEST_METHODS`:
`computes: ()`, `creates: ()`), so with the default switch every request that would change something is answered "I
cannot prepare a proposal in this app yet … Switch to act mode". To a first-time user the AI looks broken — UX-20's
symptom again, now by design.
**Options.** (a) Build proposals for computes and creates first (E7.8, D263; days). (b) Until then show what composes
shows: the switch disabled with one line, here "This app's AI acts; it cannot suggest yet", and send *act*. (c) Per-app
default. Recommendation: (b) now, (a) as planned. **Test:** `demo.cjs` asks `@ai` without touching the switch and sees
a change.
**Owner (2026-11-13):** not a P1: the AI is not fully built yet, and this is addressed with it. Deferred.

### CODE-19 · Debugging code left in the journal · P3 · new, open
`claudia_container/journal.py` keeps `_open_in_this_process` (scans every object of the garbage collector) from the
Windows CI hunt, and `_replace` sleeps up to ~10 s on Windows on the event loop (with PERF-02). The CI cause was
Controlled Folder Access. **Fix:** drop the diagnostic; move the retry off the loop with PERF-02.

**Re-checked 2026-11-24 (bug eater triage):** the scan and the retry now live in `claudia_file_writer/atomic.py` (lines 56–95), not in `journal.py`; part of the execution-model work (A1 in `notes/bug-eater-queue.md`).

### CODE-21 · One module for every computes method · P3 · new, open
`claudia_server/computes.py` is 1,228 lines: cells, names, SQL, styles, images, charts, random numbers, outcomes, search.
composes already split its lists out (`composes_lists.py`). **Fix:** one module per feature, registered on the same table.

## Round of 2026-11-15 at `078d19d`

### UX-42 · A document cannot be renamed · P2 · decided, open
Reported by the owner: Details… says "The name is sealed into the file and cannot change". **Read:** D533 binds every
sealed part, every person's key slot included, to `name:uid`. **Decided (D536):** bind to the uid alone; the owner
renames; clients keep the uid. Build: E5.21.

### UX-43 · A fenced text box becomes a container in two steps · P3 · open
**Read:** `slide-session.ts` `fenceToContainer` adds the container and then removes the box: two entries in the
history (one undo brings the box back next to the container) and the container gets a new default name, so a tag to the
box shows it as gone. **Fix:** one server request that replaces the box in one `Batch`, giving the container the box's
name.

## Code review of 2026-11-15 at `7994b00`

### CODE-28 · An app's server wiring is spread over five tables · P3 · new, open
`claudia_server/apps.py` keys five dicts by app name: `_METHODS` (23), `_ENGINES` (44), `MODEL_METHODS` (55),
`SUGGEST_METHODS` (73), `_LENSES` (76), plus `if model_cls.app == "creates"` in `methods_for` (84) and a computes-only
`workbook_context`. Changing what an app may let the AI do, or adding an app, means five edits in one file far from the
app's own code, and nothing says an app is complete.
**Recommendation:** one `AppSpec` per app (method table or factory, stand-in engine, model methods, suggest methods,
lens), declared beside the app's methods; `apps.py` keeps a registry of specs. Fits the single-server move (D430).

### CODE-29 · The server package is flat: app glue next to infrastructure · P3 · new, open
`claudia_server` has 57 modules in one folder. App-specific ones (`computes.py`, `composes.py`, `creates.py`,
`composes_lists.py`, `computes_search.py`, `composes_search.py`, `creates_search.py`, `workbook_lens.py`,
`slide_lens.py`, `standin.py`, `standin_text.py`) sit beside the gateway, hub, auth, certificates, file store and
workers. Extends CODE-21.
**Recommendation:** `claudia_server/apps/<app>/` with `methods`, `search`, `lens`, `standin` (and feature modules
for CODE-21); shared wire code (`object_methods`, `search_methods`, `rendered`, `styles`, `thing_names`) in one
`shared/` folder or at the top.

### CODE-30 · Parameters are validated twice, and a handler's bug answers `command_error` · P3 · new, open
(a) A method's parameters are a string (`"id:str row:int col:int base:revision?"`, parsed by
`protocol._parse_params`, 263) apart from the handler's keyword arguments; nothing checks that the two agree, so a
mismatch shows only when the method is called. (b) Handlers check again what the type already did, or what a type
could do: `computes._limit` (393) re-checks `number?`; `random_preview` checks `isinstance(distribution, str)` though
the spec says `str`; `_index` (206) and `_whole` (306) are one range check twice, with different messages.
(c) `MethodTable.dispatch` (416) turns every `ValueError` and `LookupError` into `command_error` with the exception's
text, because commands refuse that way: a `KeyError` from a bug in a handler looks like a refusal and is not logged.
**Recommendation:** a test that each method's parameter names equal its handler's keyword arguments
(`inspect.signature`); ranges as parameter kinds or one helper; commands refuse with `KernelError` subclasses so that
`dispatch` can log anything else as an internal error.

### CODE-31 · The history speaks English to everybody · P2 · new, open
Every command's `label` and `summary` is an English f-string (about 65 `summary` properties in core, computes,
composes and creates, e.g. "The document lets go of the shape …", `claudia_core/objects.py` 1036). `_entry_view`
(`protocol.py` 742) sends them as they are, and `SidePanel.vue` (449) shows `summary` and `origin` ("undo", "redo")
untranslated. None of them is in `po/claudia.pot`. A German user sees German menus and an English history. It is
also presentation text in the kernel.
**Recommendation:** a command describes itself as a msgid plus parameters; the server translates in the connection's
locale with `msg` (as it does for errors) or the client does. Test first: a German connection's `log` answer has no
English summary for a cell edit, a moved object and an undo.

### CODE-32 · The menu's one source lives inside the Linux shell, and the web menus are a second copy · P3 · new, open
`clients/linux/src/claudia_shell_gtk/manifest.py` is the source for the GTK menus, both Neutralino shells' menus
(`clients/{macos,windows}/tools/generate_menu.py`, two near-identical generators writing byte-identical JSON) and the
web's keys (`scripts/generate_keys.py`). It also holds the GTK XML writer (`menu_xml`). The web's menu *structure* is
written again by hand (`web/app/lib/document-menus.ts` and the three workspaces), and D361's test compares the two.
`LANGUAGES` is kept by hand in `manifest.py` and `web/app/lib/i18n.ts` (D160).
**Recommendation:** the manifest as data in a neutral place (`clients/contract/menus/` or a small package), the GTK
XML writer staying in the Linux shell; the web's menu structure generated from it like `keys.generated.ts`, each
client binding handlers by action id; one generator writing the Neutralino JSON once (with CODE-14).

### CODE-38 · computes kept the generic names, and the code uses three vocabularies · P3 · new, open
`web/app/lib/session.ts`'s `Session` and `components/Workspace.vue` are the workbook's, beside `TextSession`,
`SlideSession`, `TextWorkspace` and `SlideWorkspace`. On the server, `standin.py`'s `ScriptedEngine` is computes'
stand-in and `standin_text.py`'s `TextEngine` is composes' (it reads like a layout engine); creates' is
`NoModelEngine` in `apps.py`. Names mix the brand (`computes.py`, `composes_search.py`), the document kind
(`workbook_lens.py`, `slide_lens.py`, `SheetGrid.vue`) and the model (`WorkbookModel`, `TextModel`).
**Recommendation:** `SheetSession` / `sheet-session.ts`, `SheetWorkspace.vue`, `WorkbookStandIn`, `TextStandIn`; and
one rule written down (e.g. the brand names an app's package or folder, the document kind names the things in it).

### CODE-39 · `OpenDialog.vue` does five jobs in 1,615 lines · P3 · new, open
Server bookmarks (connect, switch, rename), the shell bridge, the document list with collections and drag and drop,
file import, recovery and details editing, plus remembered settings, in one component. `SheetGrid.vue` (1,568) and
`Workspace.vue` (1,389) are next. All 85 components sit in one flat folder.
**Recommendation:** `ServerList`, `DocumentList` (with collections) and `FileImport` as components or composables
that `OpenDialog` arranges; components grouped by app and purpose (`sheet/`, `text/`, `slide/`, `admin/`,
`dialogs/`), which Nuxt resolves with path prefixes.

### CODE-41 · Import cycles in computes are worked around with function-level imports · P3 · new, open
**Measured:** ruff's PLC0415 is off for the whole repository ("local imports break the kernel's import cycles on
purpose"); there are 44 such imports, 29 in `claudia_computes`. Two directions of knowledge cause most of them:
`CellRegion.transformed` (`region.py` 43) imports and switches on command classes, so every new structural command
means editing the region; `WorkbookModel` imports its own commands (`model.py` 488, 655) to build its first sheet and
to rename a sheet as commands.
**Recommendation:** let a command say how it moves a region (a method, or a table keyed by command kind) and move
command construction out of the model; then turn PLC0415 on per package with named exceptions.

### CODE-47 · Words of a docx with a font of their own are a `formatting` loss · P3 · new, open
**Measured** (reported as bug C, size 3): a run with its own `w:rFonts` (not through a style) keeps the paragraph
style's font and is reported as `formatting`, since the text model has no direct formatting (D306). Belongs with the
way direct formatting comes in (D379 for computes: provisional styles); until then the loss report is right.
**Batch 4** (D2004 decided, not built): a paragraph has one style and no styled words inside it, so D2004 needs those
first (`implementation-notes/bug-eater-batch-4.md` says what); a smaller step would give a paragraph whose words all have
the same font of their own a provisional paragraph style. **Postponed** by the owner (2026-11-25); the decision is
written as D2004.

### CODE-53 · The failure text of a rendered container is clipped in a small frame · P3 · open
**Read** (`RenderedFace.vue`, `.state` has `overflow: hidden`; the frame is as big as the picture was): a long message,
and the lines of the diagnostics under it, are cut off with no way to read the rest in the container. Recommendation:
the face shows the first line and the full message is in a tooltip and in the object's description, or in a popover
opened with Enter; the message stays an alert for screen readers in full. Acceptance: a test that a 300-character message
is reachable in full from the face (text in the DOM, not hidden from assistive technology).

**Re-checked 2026-11-24 (bug eater triage):** the face is `ContainerFace.vue` now (`RenderedFace.vue` is gone); `.state{overflow:hidden}` and the diagnostics cut to three are still there.

## Round of 2026-11-17 (stabilisation, `main` at `f150f0d`)

### CODE-63 · The Format ▸ Styles menu lists composes' contents styles as "custom" · P3 · new, open (read)
`TextWorkspace.vue` groups the styles of a text: headings, Body text, three called-out blocks, then `customStyles()`,
which is every paragraph style that is neither of those nor a heading. `contents-title` and `contents-1`…`contents-9`
are built-ins of composes (the look of a table of contents' lines) and are paragraph styles by kind, so they land in
the trailing "custom" group of every document. Found while replacing the web's own list of built-in ids (CODE-60).
**Fix.** Decide whether a person applies them to a paragraph at all (the contents entries take them by themselves). If
not, send a flag with each style view (`"for": "entries"`) and leave them out; this is also the way to remove the
three hand-written ids. **Acceptance.** A new text's Format ▸ Styles menu has no `Contents 1`.

### CODE-62 · A window that revives the shared server while the old one still holds the port starts it on a random port · P3 · new, open
**Measured** (found while fixing the `deb.yml` job on 2026-11-17, reported to the owner as a size 3 bug): D445 says
every app of the suite talks to one shared local server on the same port. When the server is gone, a shell window
revives it (`_keep_presence` in `clients/linux/src/claudia_shell_gtk/private_server.py`, then `desktop_server.py`). If the old server process
is still shutting down and holds the port, `free_port` chooses a random one, so the revived server lives on a port
nobody has remembered and `desktop-server.json` and `CLAUDIA_SERVER_PORT` no longer agree with it. The CI job showed
it: the window was ended after the server, revived it on a random port, and the new server then found the folder lock
of the old one ("another Claudia server uses …/documents"). The Neutralino twin, `clients/neutralino/src/private-server.ts` (then `desktop-server.ts`),
is built the same way and is likely affected (**read**, not run).
**Acceptance:** a test in which the first server still holds the port while a window revives it: the revived server
waits for the port (a bounded time) and starts on the same one; only when the port stays taken does it say so, instead
of silently using another.
**Worked around** in `deb.yml` (the window is ended first, then the server is waited for); the cause is not fixed.
**Since E8.5 part 1 (2026-11-25, `mac-installer`):** a revived server is started again on the port its page is on when
that is free; when it is held, on the next port of her range (D1621), written down as `instead`, so her apps agree on
it. The bounded wait the acceptance asks for is not built.

### SEC-19 · Imports have no memory cap · P2 · open
Imports run on `hub.workers`; `check_package` refuses bombs by declared size, but a 512 MiB package may still build a
model several times that size, in the server's own address space. **Fix.** Run import in a worker process with a
resource limit (`RLIMIT_AS`), or lower the defaults for a public demo. **Acceptance.** A hostile 500 MiB part of
many small nodes is refused with a sentence and the server stays up.
**Also:** SEC-11 (no back-off on failed logins) is P2, not P3, for as long as the demo is public.

## Round of 2026-11-19 (object interaction, branch `object-interaction`, D1221–D1231)

### UX-45 · A resize from the top or left handle is two history entries in composes · P3 · new, open
An object in a text hangs from a character and an offset (`dx`, `dy`); `resize_object` in composes takes only `w` and
`h` (`Placement.frame` is empty for `IN_TEXT`), so a handle that moves the top left corner has to send `move_object`
and `resize_object`, which are two entries and two undo steps (creates sends both in one, `x`/`y` come with the size).
**Fix.** Give `IN_TEXT.frame` the offset (`dx:int? dy:int?`) as `move` has it, and let the client send one call.
**Acceptance.** A drag of a top left handle changes the history by one entry and one Undo takes it all back (`objects.cjs`, composes, any kind; the check in step 4 of the battery says one entry for the size).
Found while building D1228.

### UX-46 · Edit ▸ Select Next Object is not built in computes (and composes) · P3 · new, open
D1063 and D1222 decide that **Tab and Edit ▸ Select Next Object (Ctrl+Alt+Shift+B) reach an object without a pointer** in
composes and computes (`notes/rotation-ui-and-the-composes-object-layer.md`). In computes Tab belongs to the cells and the
only way is Ctrl+Alt+PageDown/PageUp, which has no menu entry and so no key in the key table; in composes the objects
take Tab (`tabindex`) but the menu entry does not exist either. **Fix.** Add `edit.select-next-object` to the composes and
computes manifests with the decided key and make the computes grid step through its objects with it.
**Acceptance.** A person who uses no pointer can select, move (arrows), turn (Rotate By…) and delete an object in computes
and composes (`objects.cjs`). Found while building D1230.

### UX-47 · Delete of a selected object or table has no menu entry and no key in the key table · P3 · new, open
In composes and computes, Delete on a selected object (and, in composes, a selected table) deletes it, and the context menu
shows the hint "Del" (`web/app/lib/object-menu.ts`, written by hand). The manifest has no entry for it, so the key is in
no key table (`keys.generated.ts`, `keyboard-shortcuts.md`), the desktop menus do not show it, and BITV ("every menu entry
has a key") cannot be checked for it. Creates has `edit.delete` (`KeyOwner.VIEW`, Delete).
**Fix.** Composes: `edit.delete` as in creates, acting on the selected object or table. Computes: Delete already clears
cells, so either a second entry with the same key that acts on what is selected (object, else cells), or the cell entry
is named *Clear Cells* and Delete *Delete Object* is a separate entry; the owner decides. The context menu takes its hint
from the manifest instead of a typed string.
**Acceptance.** Edit ▸ Delete (composes) / Edit ▸ Delete Object (computes) is in the web menu and both desktop menus,
Delete is in the generated key table, and selecting an object and pressing it removes the object in one history entry
(`objects.cjs`, step "delete"). Found while auditing rotation and key coverage 2026-11-19.

### UX-48 · The object clipboard copies pictures only · P3 · new, open
D1229 gives the three apps one object clipboard (`web/app/lib/object-clipboard.ts`) for pictures. A box or a shape has
paragraph content the server cannot copy yet, and a picture from another program cannot be pasted (no import from the
system clipboard). **Fix.** A `copy_object` / `paste_object` pair in the kernel for every kind of `OBJECT_KINDS`; the web
reads image data from the paste event. **Acceptance.** Copy a box, a shape and a rendered container in each app and paste:
same body, new id, one history entry; paste an image from another program: it arrives capped as D1229 says
(`objects.cjs`, a clipboard step per kind).

### UX-49 · A table has no width handle · P3 · new, open
D1224 lists "scale the width" among what a table does as an in-flow object; D1228 builds select, move and the menu, and
leaves the width to Table options…. **Fix.** One handle on the right edge of the table frame (`ObjectFrame.vue`) that sends
the width of the table options. **Acceptance.** Drag the handle: the width changes by one history entry, and the options
dialog shows the new value (`objects.cjs`, composes, table).

### UX-50 · Composes tables have no row and column headers · P3 · new, open
The table menu of the workbook has *Height / width…* and *Insert / delete ▸* for a row or a column; composes draws no header
for them. Not part of the object work (`notes/object-interaction-contract.md`, open point 2). **Acceptance.** A header
click selects the row or column and opens the menu of the workbook; the entries do what computes' do.

### UX-51 · The words go round the unturned frame of a turned object · P2 · new, open (read)
D1226: in composes the wrap (D1061) of a turned object uses the box that holds the turned frame. Not built (D1228 says so:
nothing was turned on screen before). Since patch 10 Format ▸ Rotate works in composes, so a turned picture or box lets
words run into its corners, and Page view and print do the same. **Fix.** The layout takes the bounding box of
the turned frame (`layout/`), the editor draws the same. **Acceptance.** Turn a wrapped picture by 45° and by 90°: no line
of words enters the turned box in the editor, in Page view and in print, and the DOCX/ODT export writes the wrap of the box.
An exact outline for the wrap is a later story (D1226).

### UX-52 · A dropped object snaps to a cell border in computes · P3 · needs decision
The anchor of an object in computes is a cell (D1230): during the drag the frame follows the pointer, on release the object
goes to the nearer line at a cell border, so the position the person chose is lost. Stated as by design; entered because
the owner listed it as open. **Decision needed:** keep (and say so in the help), or let an object hold an offset inside its
cell as composes does (`dx`, `dy`), which XLSX and ODS can write (`xdr:from` offsets, `svg:x`).

### UX-53 · An object keeps its pixel size when rows or columns change · P3 · new, open
Insert, delete or resize rows and columns under a picture or a chart: the object keeps its width and height (E6.17,
D1230 "Not changed"), whereas Excel and Calc may move or scale it with the cells (`twoCellAnchor`, `table:end-cell-address`).
**Fix.** An object's *Move and size with cells* property, with the files' two modes mapped onto it. **Acceptance.** Per
mode, a row inserted above moves the object, a row resized inside it scales it or not, and the XLSX/ODS export says the same.

### CODE-68 · Computes cannot make a text box or a shape · P3 · new, open
The model can hold one on a sheet (a workbook from another app, a command from the AI) and the exports report it as `object`;
there is no Insert entry and no host support for writing in it from the sheet. **Fix.** Insert ▸ Text Box and ▸ Shape in the
computes manifest (the same entries as creates and composes), Edit text through D1232, XLSX `xdr:sp` and ODS `draw:custom-shape` export.
**Acceptance.** Insert a box and a shape in computes, write in them, export to XLSX and ODS and reimport: the same words; the loss report no longer says `object` for them.

### PROC-30 · The desktop clients were not run for this branch · P2 · new, open
Definition of done: all desktop clients work with the latest server and do not diverge from the web. For `object-interaction`
the Neutralino menus (`menu.composes.json`, `menu.computes.json`) were regenerated and the Linux manifest tests
pass; the Neutralino tests, the Windows and macOS clients and the GTK client's windows were not run. **Acceptance.**
The client tests of the three desktops pass, and a hand check on each of Format ▸ Rotate, Tools ▸ table commands and
Edit text in composes and computes is recorded in the implementation note.

## Method, this round

### SEC-22 · A viewer still receives who wrote which stretch · P2 · new, open (needs a decision)
**Evidence (read, `e2-document-sec`).** The authorship (`runs`) of every block is part of the content state: the `blocks`
method, the `text` events, the snapshot and so the viewer's own sealed file (content key) all carry it. D1261 says the
viewer's "show who wrote what" should have no data behind it. **Options.** (a) Mask `runs` for a viewer live and in her
file (a viewer's snapshot would be written without them: a second snapshot); (b) accept the authorship as content and say
so in D1261. **Proposal:** (b) until the owner says otherwise, because masking in the snapshot means the content is stored
twice. Not built either way.

### CODE-74 · `export_content` is a third kind of export nobody asked for · P3 · new, open
`export_content` (a JSON object with `format: "claudia-export 1"`) predates D1270 and is not called by any window. It is
recorded like every export (`leaves="export"`), under a format name the panel does not know. Either remove it or make it
answer with the zip; removing it changes the network API (a minor version while the major is 0).

## Round of 2026-11-20 (tracker update, `main` at `f34365f`)

### UX-60 · "Moved an object" for a move to another paragraph · P3 · new, open
D1352's mock shows the history entry of a drag to another paragraph with the object's name and the paragraph's ("Moved
Picture 1 to Paragraph 3"). The build uses the generic label "Moved an object" for every move. Belongs with UX-22 and
CODE-31 (how the history speaks). Related assumption of the same branch: a selection someone holds on an object still
names the paragraph the object was in before the move. **Acceptance.** The entry names the object and, when it changes,
the paragraph, in the user's language.

## Round of 2026-11-22 (CI of `main` after merging `architecture-improvements`; the E6.31 mockups)

### UX-68 · A sheet or a slide cannot be deleted in computes · P2 · size 2 · new, open
**Found** while drawing the mockups of E6.31 (slides in computes): the tab strip (`web/app/components/FooterBar.vue`)
renames a tab on double-click and does nothing else, and no menu entry deletes a sheet or a chart tab. The model can
(`RemoveSheet`, which refuses to orphan a chart that reads the sheet) and so can the server (`remove_chart`), but no
client calls either. A person who added a sheet by mistake keeps it. Evidence: **read** (the web client, the GTK
manifest and the web menus searched for `removeSheet`, `remove_sheet`, `removeChart`, "Delete"). After E6.31 the same
holds for a slide, except that a slide goes by itself with its last object (owner, Q20 of the chart session).
**Acceptance:** a person deletes the sheet she is on (with a question first when it holds cells or objects, and one undo
step), and is told why when a chart still reads it. The menu entry and its key wait for the menu rework against
`notes/claudia-menus.xlsx` (owner, 2026-11-22).

## Round of 2026-11-22 (Penpot file of the Styles dialog and the Search & replace dialog, branch `penpot`)

### UX-64 · Dark mode: the sidebar is not readable enough · P2 · size 2 · needs decision
Seen on 2026-11-22 when the app was looked at in the dark scheme (composes, `prefers-color-scheme: dark`, History &
Chat / Help sidebar). The symptom was reported to the owner as "dark-mode sidebar bug, size 2" but not written down;
the session that saw it was compacted before this entry. A re-check on 2026-11-22 showed the sidebar in dark mode
without one clear defect (the inactive tab "Help" and the hint texts are the dimmest candidates; not measured).
**Needs the owner to say which part he saw** (or a contrast measurement of the sidebar in both schemes). Related: the
contrast report of 2026-11-06 (`--app-dark` as literal text, see `StyleMenu.vue`). **Acceptance.** Every text in the
sidebar has contrast 4.5:1 in both schemes, measured by a test over the computed colours.

### UX-65 · Search results overflow the panel in the find-only state · P3 · size 3 · new, open
**Measured** in the running app (composes, Ctrl+H, a word with two matches): in the find-only state (no replacement
open) the results list is wider than the panel body, so the "text" badge at the end of a result row is cut off at the
panel's edge. In the replace state the rows fit. **Acceptance.** In every state of the panel the right edge of every
result row, badge included, lies inside the panel (DOM-geometry test, English and German).

## Round of 2026-11-22 (step code for the cross-app spec; branch `e2e-guard`; CODE-17 fixed above)

### UX-69 · A viewer is not told that she can only look · P2 · size 2 · open
**Measured** with the new step code of `specs/objects/the-same-in-all-three-apps.feature` (all three apps, a server
of all apps, Chromium): for a viewer, Edit ▸ Image… and Insert ▸ Container ▸ … are greyed, the Rename links of
Format ▸ All Styles… are not shown, the controls of Format ▸ Colours… are off, and dragging, scaling, turning or deleting
an object does nothing; in none of these is she told "You can only look at this document." Only Delete on an object
of a sheet says it. What D1432 promises (nothing is sent, the document and the colleague's page stay as they were)
holds everywhere. **Fix.** Tell her once when she tries: a greyed entry, a gesture on an object, the dialogs.
**Test:** the viewer scenario of that file, `@pending:UX-69` (strict: the day it passes, the tag has to go).

## Round of 2026-11-22 (E6.31 step 2: slides in computes, branch `e6-31-slides-in-computes`)

### UX-71 · Text on a workbook's slide is tiny · P2 · size 2 · needs decision
**Found** in the screenshots of `web/e2e/computes-slides.cjs`: a text box on a slide in computes is drawn in the
workbook's Body text, 13 px for the cells of a sheet, which on a slide of 1600 × 900 units is a fortieth of its height
(creates' Body text is made for a slide). Evidence: **measured** (`computes-slides-1-the-slide.png`). **Decision
needed:** whether a workbook's slides get text styles of their own (as creates has), or the slide is drawn at another
scale. Until then a person makes the text larger with a style of her own.

## Reported 2026-11-25, while designing the macOS installer (E8.5)

### CODE-99 · Another person's server is taken for one's own · P2 · size 2 · open
**Built on `mac-installer` (2026-11-25, E8.5 part 1), in review:** a person's apps use only a server that proves to be hers (D1620), on
a port of her account (D1621); scenarios of `desktop/private-place.feature` marked `# CODE-99`, tests in
`clients/neutralino/tests/private-server.test.ts` and `clients/linux/tests/test_private_server.py`.
**Read:** `DesktopServer.ensure()` takes any Claudia server that answers on 8765 (or the remembered port) and serves the
window's app at the same version as this computer's server, "whoever started it". On a computer with two people logged in
(fast user switching on macOS and Windows, two sessions on Linux), the second person's windows use the first person's
server: her new documents are written into the first person's home folder, as the first person's files, and she sees the
list of the first person's documents. When the first person logs out, the server goes, the second person's apps start her
own, and her earlier documents seem lost. With a service running (D743, Windows) every person's apps use the service's
documents instead of their own. **Acceptance:** a scenario with two people on one computer, each with her own documents,
where neither sees the other's list and each finds her own documents again after the other has logged out.

### CODE-100 · A service of another version locks the apps out · P2 · size 2 · open
**Built on `mac-installer` (2026-11-25, E8.5 part 1), in review:** a server that is not hers is never compared with her version
(D1620); scenario of `desktop/private-place.feature` marked `# CODE-100`, same tests.
**Read:** `checkIsOurs` refuses a Claudia server of another version and tells the person that it "stops by itself ten
minutes after its last window has closed". A service never does. Windows: an install "only for me" that is newer than an
all-users install with the service; macOS: `./start-mac-client.sh` next to an installed service. The apps cannot start
until someone stops the service. **Acceptance:** a scenario with a service of another version on the computer, where the
person's apps start her own server and open.

## Found in batch 3 of the bug eater (2026-11-25; branch `batch-3`)

### UX-91 · In Firefox the down arrow does not go into a new table · P2 · size 2 · open
**Measured** by the first Firefox job that ran (CI on `batch-3`, twice): `test_objects_in_composes.py::
test_i_can_work_in_a_new_kind_straight_away[table]` fails at "Ctrl+Home, End, ↓": no box has the caret
("expected 'r1/c1', the page shows None"); 44 other scenarios pass in Firefox. Read, not run (Firefox cannot be
installed in this workspace, and CI's screenshots cannot be downloaded from it): the editor decides that the caret is on
the last line of the paragraph from the rectangle of the collapsed selection (`onEdgeLine` in `TextEditor.vue`), which
Firefox reports differently at the end of a line. A first guess (the table not there yet when it was inserted) was
tried on CI and was wrong. **Until it is fixed** (the owner, 2026-11-25) the scenario "I can work in a new <kind>
straight away" of `invariants/objects-in-composes.feature` carries no `@firefox` tag; put it back with the fix.

## Found after batch 3 of the bug eater (2026-11-25)

## Found in batch 4 of the bug eater (2026-11-25)

Logged by the owner's word of 2026-11-25. "Helper" means a helper of batch 4 found it while fixing CODE-66, CODE-70 or
PROC-37; the evidence label says how far it was checked.

### SEC-24 · An owner's export carries private chat messages · P2 · size 2 · open
**Read:** `_export_claudia` in `claudia_server/protocol.py` writes `chat_payloads(ctx.document.chat)`, every message,
when an owner exports with the history; the `chat` method gives each person only the messages for everybody and those
to or from her (`readable`, same file). So an owner's file holds private messages between two other people that she
cannot read in the document, and anybody she gives the file to can. (D2005 already keeps private messages out of the
note an imported export brings; this is the export itself.) Found by a helper (PROC-37), confirmed by reading.
**Acceptance:** an export of a document in which Ben wrote privately to Cleo holds no such message when Ann exports it;
one Ann wrote or received privately, the owner decides (keep, or leave out too).

### SEC-25 · An editor can replace the document with a raw `Import` · P2 · size 2 · open
**Read:** `apply` (`_apply` in `protocol.py`) decodes any command the registry knows and executes it as the editor; it
refuses only the assistant (SEC-10). `core.Import` is such a command, so an editor can replace the whole content, and
since D2005 also give it a forged `original` ("History of the original" with words nobody said). The app's own import
path is an owner's upload. Found by a helper (PROC-37), confirmed by reading. **Acceptance:** `apply` with an `Import`
from an editor is refused (`forbidden`), and the history is unchanged; the owner says whether any other command is
for the server's own use only.

### UX-93 · The font banner cannot be read · P2 · size 2 · open
**Measured** in Chromium (batch 4, opening a pptx in creates): `[data-testid=font-banner]` has the background
`rgb(42, 35, 66)` (the fallback of `--panel-2`, which is not defined) and the text `rgb(31, 26, 51)` (`--ink`): a
contrast of about 1.1:1. BITV 1.4.3 asks 4.5:1, so this is a divergence from the standard. `FontReportBanner.vue` was
not changed by batch 4 (its wrapper for UX-90 has no style). **Acceptance:** the banner's text and its links and
buttons reach 4.5:1 in light and dark mode, checked by a test of the computed colours.

### UX-92 · History & Chat says "undo" and "redo" in English · P3 · size 3 · open
**Read:** `SidePanel.vue` shows `{{ row.entry.origin }} ·` before an undone or redone step, the raw `undo` or `redo`;
the "History of the original" (D2005) copies the same words into its lines on the server. Close to CODE-31 (the
summaries are English too), but these two words are the web's own. **Acceptance:** with German chosen, the panel says
"Rückgängig ·" / "Wiederholt ·" (or the agreed words); the note of an imported export keeps the origin apart from the
words, so the reader's language says it.

### CODE-101 · A pptx placeholder's inherited size and alignment are lost silently · P3 · size 2 · open
**Read** while fixing CODE-45 (and seen in the browser: the title of a "Title and Content" slide comes in at the size of
body text, left aligned). A placeholder takes its size and alignment from its layout and master (a title's 44 pt,
centred); the import reads only the bullet (CODE-45) and the font (`_pptx_fonts`), and `pptx_import_losses` reports
nothing (CODE-45's acceptance). An explicit size on a run is a `look` loss; an inherited one is not seen at all.
**Acceptance:** the title of the default "Title and Content" slide comes in centred and at its size, or the import says
that its size is not kept.

### CODE-102 · A pptx box with several bulleted paragraphs has one bullet · P3 · size 2 · open
**Measured** in the browser (batch 4): a body placeholder with "First point" and "Second point" shows a bullet before
the first only. The model holds one paragraph per box, with one list item, and the import joins the paragraphs with
line breaks; it reads the bullet of the first paragraph only. Text boxes always did so; CODE-45 makes it common, as
every body placeholder is bulleted. Nothing reports it. **Acceptance:** a box of three bulleted paragraphs comes in
with three bullets, or the import says that the bullets after the first are not kept.

### CODE-103 · ods: a chart in a cell moved and described in one export is written anew · P3 · size 3 · open
**Read** by a helper (CODE-66), not reproduced: in `ods_chart_patch`, a chart frame anchored in a cell that is both
moved and given a description since the import gets two edits of the same element; the patch raises `UnsupportedEdit`
and the export falls back to a fresh file (`not-patched`), losing what the kept file had beyond the model.
**Acceptance:** that export patches the kept file, with the chart at its new place and with its description.

### CODE-104 · Pictures of a file LibreOffice wrote are not read in · P3 · size 3 · open
**Measured** by a helper (CODE-66) with LibreOffice: an xlsx that LibreOffice wrote from one of our files comes in
without any of its pictures; such an ods loses the turned ones. Files we write, fresh or patched, are read back with
their pictures. The cause was not found. **Acceptance:** a picture (and a turned one) of an xlsx and an ods that
LibreOffice saved comes in at its place.

### CODE-105 · docx: a paragraph mark's run properties count as a loss · P3 · size 3 · open
**Measured** by a helper (CODE-47 analysis): a docx paragraph whose mark has run properties of its own (`w:pPr/w:rPr`,
which Word writes for nearly every paragraph) is counted as a `formatting` loss, though the properties of the mark are
not visible in the text. So the import over-counts what it leaves out. **Acceptance:** a docx whose only run properties
are those of paragraph marks reports no `formatting` loss.
