# Bug-eater queue

Triage of every open item of `bugtracker.md`, checked against the code of `backlog` at `8a97b7a` on 2026-11-24 (read,
not run, unless the evidence says so). The status column of the tracker was not trusted. Nothing in the tracker is
re-marked by this note: it is a **proposal**, and an item changes its status in the tracker only once the owner agrees
(`bug-eater.md`).

Columns: **Real?** — does the problem still exist in the code; **Class** — fix-now, needs-decision, architecture,
close; **Size** — 1 huge, 2 medium, 3 small; **First test** — the test that has to fail before the fix.

## 1. Proposed for closing (owner to agree)

| ID | Why |
|---|---|
| CODE-17, CODE-75, CODE-76 | Already marked fixed, but still listed under *Open* |
| CODE-35 | `BaseSession.write()` exists once (`base-session.ts:1231`, D1432); the 11 `attempt` writes left in `text-session.ts` are D1432's stated exceptions |
| CODE-37 | One `ImageImportDialog.vue` with an `add` prop; `SheetImageImportDialog.vue` is gone |
| CODE-69 | Superseded: `ObjectBody.paragraph` is already the shared paragraph with a style and author runs (D181, E10.17). Only the per-host overflow policy is left; re-file it if wanted. `implementation-notes-shared-object-layer.md:107` still says "plain `str`" and needs correcting |
| UX-06 | Superseded: D4 is superseded by D120, which says it resolves UX-06 |
| UX-09 | Fixed: `shim.js` was retired with D121; the rest is CODE-32 |
| UX-27 | Fixed: `insertFrame` shifts each new object by 32 px (`geometry.ts:116-127`) |
| UX-07, WEB-02 | Website items; the website is not in this repository (as with WEB-01, deleted on the owner's word 2026-11-24) |
| UX-54 | The admin pages are navigation, not menu entries, so the shortcut rule does not apply (proposal) |
| UX-59 | Measured once, not seen again; no code change tied to it. Close, or re-measure 20 runs without the wait |

## 2. Decisions the owner is asked for (with a proposed default)

| ID | Question | Proposed default |
|---|---|---|
| SEC-09 | Confusable user names: refuse or warn? | Refuse a name that mixes scripts; warn when two names in a document are confusable |
| SEC-22 | A viewer receives who wrote which stretch | Accept authorship as content and say so in D1261 (the tracker's proposal; masking would store the content twice) |
| PROC-22 | LibreOffice CI job: make it blocking? | Yes: 31 of 31 files read in every round; log the LibreOffice version |
| PROC-30 | What "the desktop clients were run" means for a batch | The CI jobs `neutralino-*` and `linux-client` green, plus one recorded hand check on the GTK client per batch that touches the UI |
| PROC-37 | History and chat of an imported export | (a): one read-only note "History of the original", names as text |
| CODE-31, UX-22, UX-60 | Where the history is translated, and one rule for its sentences | The server sends a message id and arguments, the client translates (as the refusals of CODE-78 do); one rule: past tense, a name not an id |
| CODE-38 | A naming rule for app-specific classes | `ComputesSession`, `SheetWorkspace.vue`; stand-ins named `<Kind>StandIn`; written into `coding-standards.md` |
| CODE-47 | A docx run with its own font | Extend D379's provisional styles to composes |
| CODE-63 | Contents styles listed as "custom" | Hide built-in generated styles from the custom list |
| CODE-68 | Text boxes and shapes on a sheet | Not on a sheet (D1232 stands); only on a workbook's slide |
| CODE-74 | `export_content` answers an undocumented JSON | Remove the method (its only client is never called) |
| UX-23 | Undo in a different place in each app | Mock-up first, then one place in all three |
| UX-34 | The AI refuses every change in computes and creates by default | Disable the act/propose switch there, with one line, until E7.8 builds proposals |
| UX-47 | Delete for an object in composes and computes | composes copies creates' `edit.delete`; computes adds Edit ▸ Delete Object on Delete, on only while an object is selected, Clear Cells stays for cells |
| UX-50 | Row and column headers on composes tables | Mock-up first |
| UX-52, UX-53 | How a computes object is anchored | One decision: an anchor with an offset and a "move and size with cells" mode, mapped to xlsx `oneCellAnchor` / `twoCellAnchor` |
| UX-64 | Dark-mode contrast in the side panel; the symptom was never written down | Make the acceptance the spec: every sidebar text ≥ 4.5:1 measured in both schemes |
| UX-68 | Deleting a sheet or a slide in computes | Edit ▸ Delete Sheet… beside Rename Sheet…, and the same on the tab strip (key to be added to `claudia-menus.xlsx`) |
| UX-71 | Text on a workbook's slide is tiny | A workbook's slides use creates' slide text styles |

## 3. Proposed batches

Each batch is one branch and one decision-id range. The order puts small, certain work first, so the loop gets tried
out on low risk.

| # | Batch | Items | Notes |
|---|---|---|---|
| 1 | **Small and certain** | SEC-06, SEC-14, SEC-16, CODE-20, CODE-36, CODE-54, CODE-56, CODE-71, UX-32, UX-63, UX-66, UX-67, UX-74, UX-75, PROC-31, plus PROC-15: a guard that no row under *Open* says fixed | All size 3, no decision needed |
| 2 | **Tests that tell the truth** | PROC-40 (bind the last two spec files, among them the invariants), PROC-29, UX-69, UX-76, PROC-22 (if agreed), E2E in Firefox on CI | See section 5 |
| 3 | **What leaves and comes back** (export and import losses) | UX-70, CODE-25, CODE-66, CODE-70, CODE-84, CODE-45 (size 1, may become its own batch), CODE-47, PROC-37 | CODE-66 and CODE-70 have one fix: the patch of a kept xlsx/ods learns to add parts |
| 4 | **The object layer** | UX-43, UX-45, UX-49, UX-51, then UX-52/53 and UX-50 once decided | UX-48 (copying every kind of object) is architecture |
| 5 | **Small UX after decisions** | UX-08, UX-23, UX-34, UX-64, UX-65, UX-71, CODE-03, CODE-06, CODE-53, CODE-62, CODE-63, CODE-74, SEC-09, SEC-22, CODE-04 (`claudia-core` first) | After the answers of section 2; CODE-38 goes with A2 and A4, CODE-68 is closed if the default stands, PROC-30 is a rule for every batch |
| 6 | **The history in the reader's language** | CODE-31, UX-22, UX-60 | Size 1; needs the decision in section 2 |
| — | Architecture track | below | Not done as bug fixes |

## 4. Architecture track

Each one gets a design pass (class diagram, Fable's second opinion, the owner's agreement) before any code.

| # | Root cause | Items it removes | The change in one sentence |
|---|---|---|---|
| A1 | **Execution model:** slow work runs on the one event loop that serves every document | PERF-02, PERF-06, PERF-10, SEC-19, CODE-19 | A `DocumentExecutor` per document (the open design of 2026-11-20): group commit of the journal off the loop, packing and outcomes in the worker pool, a memory cap on the import worker, results checked against the revision before they land |
| A2 | **Server structure:** app wiring spread over six tables and 80 flat modules | CODE-21, CODE-28, CODE-29, CODE-30, the server half of CODE-38 | One `claudia_server/apps/<app>/` package per app declaring one `AppSpec`; refusals raised as typed errors, so a handler's bug is no longer a `command_error` |
| A3 | **One source for menus:** the manifest lives inside the GTK shell, the web menus are a hand-written copy | CODE-32, CODE-71, UX-46, UX-47, UX-68 (the menu half) | A neutral manifest from which the GTK, Neutralino and web menus, key hints and `LANGUAGES` are generated; to be done together with the menu rework of `claudia-menus.xlsx` |
| A4 | **Web structure** | CODE-39 (and CODE-36 from batch 1) | Component folders by app and purpose, `OpenDialog.vue` split into server list, document list and file import |
| A5 | **Kernel dependencies:** 49 function-level imports work around import cycles, 32 of them in computes | CODE-41 | Break the cycle `region.py` ↔ commands; ruff PLC0415 on for `claudia_computes` with named exceptions only |
| A6 | **Document identity** | UX-42 | Decided (D536); build story E5.21 |
| A7 | **Copying objects** | UX-48 | `copy_object` / `paste_object` for every kind of object, not only pictures |
| A8 | Computes recalculation | PERF-07 | Rewrite only the formulas that refer to the edited sheet |
| A9 | Web bundle | PERF-08 | A Plotly bundle with only the trace types claudia uses, guarded by a size check |

Proposed order: A1 first (it decides how every later server change runs), then A2, then A3 with the menu rework.

## 5. Domain language

Story E1.18 already holds the plan; next on branch `e1-18-remaining-names` (range D1430–D1449) are **ai**, then
**proposal**. What the code says today:

- "suggest" appears on 575 lines: `claudia-server` 186, `claudia-composes` 133, `claudia-composes-io` 119 (mostly Word's
  tracked changes, which are rightly called something else), `web/app` 119, clients 12. It is in the wire API too:
  `suggest`, `suggest_words`, `SUGGEST_METHODS` (`apps.py:90`), and the AI mode value `suggest`.
- The What-if is built on `Document.scratch()` (`claudia-core`, `document.py:458`); "scratch copy" is the glossary's
  word to avoid. The UI does not use it.
- `assistant` (`assistant.py`) is the glossary's **ai**.
- **Proposals do not exist in computes and creates** (`SUGGEST_METHODS` is empty for them; UX-34). This is the part
  that is missing as a sub-domain, not only as a name; it is story E7.8 and needs its own design, so it is not part of
  the rename.

Proposal: first the rename (ai, then proposal and propose, including the wire methods and the stored mode value, with no
compatibility layer while claudia is pre-release), done by a sub-agent as a sweep with the tests as the safety net;
then E7.8 as a feature with grilling, mocks and specs.

## 6. Where the test suite is weak

Line coverage is not the problem: the Python packages are held at 88–100 %, the web app's `app/lib` at 85 % of
statements. The weak spots are elsewhere:

1. **The shared invariants suite runs nowhere.** It exists only for composes
   (`specs/invariants/objects-in-composes.feature`, 12 scenarios) and is still in `NOT_BOUND_YET`. There is none for
   computes and creates, though the invariants are meant for every object type.
2. **CI runs the E2E specs in Chromium only.** Firefox is the main test browser, but `run_e2e.py` defaults to
   `chromium` and CI never passes `--browser`.
3. **The Vue components are measured by no coverage**: 111 components, about 30,600 lines, against 19,800 lines in
   `app/lib`; only the E2E scripts reach them.
4. **Two people at once** is asserted only for arrival (PROC-29); the outline, name tag and the refused drag of a held
   object are not.
5. **21 scenarios are `@pending`.**
6. **The desktop clients** are tested in CI, but whether a feature was checked in them is not recorded (PROC-30).
7. **Assertion strength is unknown.** High coverage says code was reached, not that a wrong result would fail a
   test. Proposal: a mutation-testing probe (`mutmut`) on `claudia-core` and one app package, to see how many mutants
   survive, before deciding where to add tests.

Proposal for batch 2: bind the invariants for composes and write them for computes and creates, run the specs in
Firefox on CI (both browsers for `@core`), and the mutation probe as a measurement reported to the owner.

## 7. The tracker itself

Found while checking (to be fixed in batch 1 under PROC-15):

- CODE-17, CODE-75 and CODE-76 are listed under *Open* with status fixed.
- The *Open* table is not in the stated order: UX-64 (P2) sits among the P3 items, and UX-74, UX-75 and CODE-84 come after
  CODE-76. CODE-53 and CODE-63 carry the categories "Web" and "UX / composes".
- Stale evidence: CODE-19 is now in `claudia_file_writer/atomic.py`, not `journal.py`; CODE-53 names
  `RenderedFace.vue`, now `ContainerFace.vue`; counts have grown (CODE-21 1,321 lines, CODE-28 six tables, CODE-29 80
  modules, CODE-39 110 components, CODE-41 49/32 imports); UX-68's section heading still says "chart tab".
- UX-08 and UX-23 are partly fixed (Create is apart from Open; the suggestion list moved to the footer).

## 8. Every item

| ID | Real? | Evidence | Class | Cluster | Size | First test |
|---|---|---|---|---|---|---|
| SEC-06 | yes | `certs.py:100` `BasicConstraints(ca=True, path_length=0)`, no `NameConstraints` | fix-now | certificates | 3 | unit: a certificate for another name signed by the server's key fails verification; a pinning client still connects |
| SEC-09 | yes | `crypto.py:147` NFKC + casefold only; Cyrillic а ≠ Latin a | needs-decision | names | 3 | unit: "аnna" (Cyrillic а) beside "anna" is refused or flagged |
| SEC-14 | yes | `app.py:766` `docs_url="/api/swagger"`, linked from the landing page (`app.py:170`) | fix-now | privacy | 3 | api: `/api/swagger` is 404 by default; no page names a third-party host |
| SEC-16 | yes | `admin_api.py:522-527` stores any path; `--version` is asked only when typesetting (`engine.py:76`) | fix-now | admin-settings | 3 | api: `PUT /settings/typeset` with `/bin/true` is refused with a sentence |
| SEC-19 | yes, narrower | imports run in worker processes (`workers.py`), so a crash is isolated; no `RLIMIT_AS` anywhere | architecture (A1) | execution-model | 2 | server: an import that builds a huge model is refused, the server keeps answering |
| SEC-22 | yes | authorship `runs` part of the content state | needs-decision | viewer-rights | 2/3 | api: a viewer's `blocks` has no `runs` (only if masking is chosen) |
| PERF-02 | yes | `journal.py:194` `os.fsync` in `append`, called synchronously from `connection.handle` | architecture (A1) | execution-model | 1 | server: with an append that sleeps 50 ms, another user's `ping` answers < 20 ms |
| PERF-06 | yes | `sealed.py:675-680` `_pack` on the loop every 500 changes | architecture (A1) | execution-model | 2 | server: packing a large document does not delay another document's `ping` |
| PERF-07 | yes (documented) | structure edits rewrite every formula | architecture (A8) | computes-recalc | 2 | perf guard: a row inserted in 100k formulas < 1 s |
| PERF-08 | yes | `plotly.js-dist-min` (`ChartView.vue:37`) | architecture (A9) | web-bundle | 3 | build check: chart chunk ≤ 1.2 MB |
| PERF-10 | yes | `outcomes.py:51,382` synchronous, `MAX_WORK = 2_000_000` | architecture (A1) | execution-model | 2 | server: an edit in the what-if model answers < 200 ms, an `outcomes` event follows |
| PROC-15 | yes | three fixed rows under *Open* | fix-now | tracker | 3 | a test: no row under *Open* has status fixed |
| PROC-22 | yes | `ci.yml:199` `continue-on-error: true` | needs-decision | ci | 3 | — |
| PROC-29 | yes | step 8 of the battery asserts arrival only | fix-now | multi-user-e2e | 2 | e2e: page 2 sees page 1's outline and name tag while page 1 holds the object |
| PROC-30 | yes | no per-feature record of the desktop clients | needs-decision | clients | 2 | — |
| PROC-31 | unclear | `extract_i18n.py:255` still writes `#:` locations; not re-measured | fix-now | i18n-tooling | 3 | test: moving a line of a translated file leaves the catalogue check green |
| PROC-37 | yes | `import_state` takes only `state` | needs-decision | export-import | 2 | io: importing an owner's export adds one note with who did what |
| PROC-40 | partly fixed | guard exists (`test_specs_are_bound.py:27`); `document-file/requirements.feature` and `invariants/objects-in-composes.feature` still unbound | fix-now | spec-binding | 2 | `NOT_BOUND_YET` empty |
| CODE-03 | yes | `README.md:9-16` names 6 of 18 packages, no `clients/` | fix-now | docs-drift | 3 | structural: every package and client directory is named in the README |
| CODE-04 | yes | no `disallow_untyped_defs`; 321 unannotated functions (server 188, computes 99, core 26) | fix-now (core first) | typing | 2 | mypy with `disallow_untyped_defs` on `claudia_core` gives 0 errors |
| CODE-06 | yes | `cli.py:218` `--max-connections` checked per room (`hub.py:492`) | fix-now | server-cli | 3 | unit: the flag's help says per document |
| CODE-17 | no-fixed | `web/e2e/browser.cjs`, guarded by `test_run_e2e.py:42` (D1453) | close | e2e-tooling | 3 | (exists) |
| CODE-19 | yes (moved) | gc scan and ~10 s retry now in `claudia_file_writer/atomic.py:56-95` | architecture (A1) | execution-model | 3 | unit: no `time.sleep` on the loop thread, no `gc.get_objects` in src |
| CODE-20 | yes | `Dockerfile:27` `uv:latest` | fix-now | supply-chain | 3 | structural: no `:latest` in the Dockerfile |
| CODE-21 | yes | `computes.py` 1,321 lines, 75 functions | architecture (A2) | server-structure | 2 | structural: module size cap in `claudia_server` |
| CODE-25 | yes | pptx/odp writers set no object names; odp pages are `pageN` (`odp.py:1093`) | fix-now | export-losses | 2 | api: renamed object and slide survive a pptx/odp round trip |
| CODE-28 | yes (worse) | `apps.py` six app-keyed tables and three `app ==` branches | architecture (A2) | server-structure | 2 | structural: each app registers one complete `AppSpec` |
| CODE-29 | yes (worse) | 80 flat modules in `claudia_server` | architecture (A2) | server-structure | 1 | structural: no app module at the top level |
| CODE-30 | yes | `protocol.py:511-516` every `ValueError`/`LookupError` → `command_error` | architecture (A2) | server-structure | 2 | unit: spec parameters equal each handler's signature; a handler's `KeyError` is logged as internal |
| CODE-31 | yes | `protocol.py:956-957` English label and summary; 87 summaries | needs-decision | history-i18n | 1 | api: a German connection's `log` has no English summary |
| CODE-32 | yes (partly) | manifest in `clients/linux/.../manifest.py` (1,400 lines); web menus hand-written (`document-menus.ts`); `LANGUAGES` twice | architecture (A3) | menu-single-source | 2 | structural: web menus and `LANGUAGES` generated from one manifest |
| CODE-35 | no-fixed | `BaseSession.write()` once (D1432) | close | web-session | 3 | (exists) |
| CODE-36 | yes | six `safeStorage()` copies, three `remembered()` | fix-now | web-duplication | 3 | structural: defined only in `lib/storage.ts` |
| CODE-37 | no-fixed | one `ImageImportDialog.vue` | close | web-duplication | 3 | — |
| CODE-38 | yes | `class Session`, `Workspace.vue`, `ScriptedEngine`, `TextEngine`, `NoModelEngine` | needs-decision | naming | 2 | structural: no unqualified `Session` / `Workspace.vue` |
| CODE-39 | yes (worse) | `OpenDialog.vue` 1,625 lines, 110 components in one folder | architecture (A4) | web-structure | 2 | structural: component line cap |
| CODE-41 | yes (worse) | 49 function-level imports, 32 in computes; PLC0415 off | architecture (A5) | kernel-dependencies | 2 | ruff PLC0415 on for `claudia_computes` |
| CODE-45 | yes | `pptx._classify` (`pptx.py:518-528`) drops placeholders | fix-now | import-gaps | 1 | api: a "Title and Content" deck imports title and body |
| CODE-47 | yes | `docx.py:638` any `w:rPr` → `formatting` loss | needs-decision | import-gaps | 2 | api: a run with its own font imports with it, no loss |
| CODE-53 | yes | now `ContainerFace.vue:58` `overflow:hidden`, diagnostics cut to 3 | fix-now | render-ui | 3 | e2e: a 300-character failure can be read in full |
| CODE-54 | yes | `service.py:87-91` cache key without the font catalogue | fix-now | render-cache | 3 | unit: replacing a font makes the next draw not cached |
| CODE-56 | yes | `_fresh_sheet_id` counts from `len(tabs)+1` (`computes.py:580-586`) | fix-now | id-allocation | 3 | api: add s2, s3, remove s3, add: not s3 |
| CODE-62 | yes | `desktop_server.py:439-444` and `desktop-server.ts:366` take a free port at once | fix-now | desktop-server | 2 | unit: waits (bounded) and restarts on the remembered port |
| CODE-63 | yes | `TextWorkspace.vue:637,653` lists `contents-*` as custom | needs-decision | styles | 3 | e2e: no "Contents 1" in a new text's custom styles |
| CODE-66 | yes | `_unwritten.py:25` `FRESH_ONLY` holds pictures | fix-now | kept-file-patch | 2 | api: a picture added to an imported xlsx/ods is in the export |
| CODE-68 | yes (partly superseded) | boxes on a slide (D1479) but not on a sheet | needs-decision | shared-objects | 2 | — |
| CODE-69 | no-superseded | `ObjectBody.paragraph` is the shared paragraph (D181) | close | shared-objects | 3 | — |
| CODE-70 | yes | `FRESH_ONLY` holds pivots | fix-now | kept-file-patch | 2 | api: a pivot defined in an imported file is in the export |
| CODE-71 | yes | `object-menu.ts:68,89,95` four hand-typed hints | fix-now | menu-single-source | 3 | unit: every context-menu hint equals the manifest key |
| CODE-74 | yes | `protocol.py:1303-1310` `"claudia-export 1"`; client never calls it | needs-decision | dead-api | 3 | api: `export_content` gone from `/api/protocol` |
| CODE-75 | no-fixed | `base-session.ts:1231-1234`, tested | close | web-session | 3 | (exists) |
| CODE-76 | no-fixed | `base-session.ts:1103` | close | web-session | 3 | (exists) |
| CODE-84 | yes | `pptx.py:90-97`, `odp.py:115-129,293` own copies | fix-now | shared-io-code | 3 | structural: no preset or graphic-style reader in `claudia_creates_io` |
| UX-06 | no-superseded | D4 superseded by D120 | close | menu-single-source | 3 | — |
| UX-07 | unclear | website not in this repository; the web app's viewport is fine | close | website | 3 | — |
| UX-08 | yes (partly) | Create is apart; Open still says "name or password is not right" (`OpenDialog.vue:787`) | fix-now | open-dialog | 3 | e2e: a name not in the server's list says so |
| UX-09 | no-fixed | `shim.js` retired (D121) | close | menu-single-source | 3 | — |
| UX-22 | yes | `add sheet {name}`, `new paragraph`, `Moved an object` | needs-decision (with CODE-31) | history-i18n | 2 | unit: every command's summary follows the rule |
| UX-23 | yes (partly) | undo in FormulaBar and InsertBar, none in composes | needs-decision | panel-consistency | 3 | e2e: undo at the same place in all three |
| UX-27 | no-fixed | `geometry.ts:116-127` | close | object-layer | 3 | — |
| UX-32 | yes | `DocumentFrame.vue:189` `<div class="main">`, no `<main>` | fix-now | a11y | 3 | e2e (axe): `landmark-one-main` and `region` pass in each app |
| UX-34 | yes | `SUGGEST_METHODS` empty for computes and creates; default `'suggest'` (`ai-mode.ts:7`) | needs-decision | ai-proposals | 3 / 1 (E7.8) | e2e: in computes, `@ai` with the switch left alone acts or the switch is off with one line |
| UX-42 | yes | `DetailsDialog.vue:38` "sealed into the file"; no `rename_document` | architecture (A6) | document-identity | 1 | api: `rename_document` keeps the uid, refused for an editor |
| UX-43 | yes | `slide-session.ts:258-271` two requests, new name | fix-now | object-layer | 3 | api: box → container is one entry, one undo, name kept |
| UX-45 | yes | `composes.py:639` `frame=""`, no `dx`/`dy` | fix-now | object-layer | 3 | api: resize from the top-left is one entry |
| UX-46 | yes | no `edit.select-next-object`; computes has a local `view.nextObject` | fix-now | menu-single-source | 3 | unit: composes and computes manifests have it |
| UX-47 | yes | `edit.delete` only in creates | needs-decision | menu-single-source | 3 | unit: a Delete entry for objects in all three |
| UX-48 | yes | `object-clipboard.ts:1-2` pictures only | architecture (A7) | object-layer | 2 | api: copy and paste a text box and a shape |
| UX-49 | yes | `TextObjectLayer.vue:216` skips tables, no frame | fix-now | object-layer | 3 | e2e: the right-edge handle changes a table's width in one entry |
| UX-50 | yes | no row or column header strips | needs-decision | object-layer | 2 | e2e: a column header selects the column |
| UX-51 | yes | `layout/src/apps/composes.ts:449-454` ignores rotation | fix-now | object-layer | 2 | unit (layout): a turned object keeps its rotated box free of text |
| UX-52 | yes (by design) | `CellAnchor` has no offset (`model.py:96-106`) | needs-decision | cell-anchor | 2 | api: an offset survives an xlsx/ods round trip |
| UX-53 | yes (by design) | `model.py:82-85` anchor never changes | needs-decision | cell-anchor | 2 | api: "move and size with cells" moves the object when a row is inserted |
| UX-54 | yes | admin pages have no shortcut (`AdminShell.vue:43-44`) | close (proposal) | a11y | 3 | — |
| UX-59 | unclear | measured once | close or re-measure | caret | 3 | e2e: 20 runs without the wait |
| UX-60 | yes | `objects.py:1363-1365` always "Moved an object" | fix-now (with UX-22) | history-i18n | 3 | unit: the summary names object and paragraph |
| UX-63 | yes | `PrintPreview.vue:359` "recorded in the document's history" | fix-now | wording | 3 | unit: the note names the exit record |
| UX-64 | unclear | symptom never written down; not measured | needs-decision | dark-mode | 2 | sidebar text ≥ 4.5:1 in both schemes |
| UX-65 | yes (not re-measured) | no CSS change to the result rows since filed | fix-now | layout-css | 3 | e2e: every result row and badge inside the panel, EN and DE |
| UX-66 | yes | `StylesDialog.vue:233` `#7a4710`; no `--apricot-dark` token | fix-now | tokens | 3 | unit: no colour literal outside `tokens.css` |
| UX-67 | yes | `StyleSpec.vue:211,217` unclassed `<select>` | fix-now | a11y | 3 | e2e: field border, focus ring, axe contrast |
| UX-68 | yes | nothing reaches `RemoveSheet` / `RemoveSlide` | needs-decision | menu-single-source | 2 | api: `remove_sheet` removes in one undoable step |
| UX-69 | yes (partly) | gestures give a notice in places; scenario still `@pending:UX-69` | fix-now | viewer-rights | 2 | e2e: the `@pending:UX-69` scenario |
| UX-70 | yes | `ExportedFile.losses` (`base-session.ts:41`) read by no component | fix-now | export-losses | 2 | unit: the download dialog names each loss once |
| UX-71 | yes | no slide text styles in computes | needs-decision | computes-slides | 2 | e2e: cap height on a computes slide ≥ creates' |
| UX-74 | yes | `ai-provider.ts:83` `'no-remote'` when not offered | fix-now | ai-consent | 3 | unit: an existing consent can be cleared |
| UX-75 | yes | `AiRuntime.apply` (`admin_api.py:143-170`) publishes nothing | fix-now | ai-consent | 3 | api: open documents hear a provider change |
| UX-76 | yes | `Workspace.vue:1330` no default name | fix-now | names | 3 | e2e: the `@pending:UX-76` scenario |
| WEB-02 | yes | the website is not in this repository | close | website | 3 | — |
