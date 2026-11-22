# Claudia — bug tracker

Moved here from the project context on 2026-11-05 (was `qa-bug-tracker.md`). This file is the tracker; the review that
produced the current round is `qa-recommendations.md`. Stories are in `Projects/claudia-office/_tasks/` (E-numbers), decisions in
`decision-log/` (D-numbers).

**Review rounds:** first 2026-11-02 at `f8df891`; second 2026-11-05 at `54d1245` ("E5 desktop clients: linux first
draft"). Statuses below were re-checked against `54d1245` on 2026-11-05 — every item marked *verified open* or *verified
fixed* was re-tested or re-read in that tree, not carried over on trust. Fourth round 2026-11-12 at `7e619a2` (all
feature branches merged): new items UX-20 to UX-23, SEC-12 to SEC-17, PERF-08, PROC-09 to PROC-16, CODE-13 to CODE-15 (and in the follow-up on `e56e8f9`: UX-24 to UX-27, PROC-17, CODE-16);
the statuses of SEC-11, PERF-01, PERF-02, PERF-05 and UX-01 to UX-05 were re-checked in that tree
(`qa-recommendations.md`). Fifth round 2026-11-13 at `cfa2d91` (all feature branches merged: printing, lists, search, random numbers and
scenarios, i18n, BITV): new items SEC-18, PERF-09 to PERF-11, UX-33 to UX-37, PROC-18 to PROC-22, CODE-17 to CODE-21,
DOC-02; the `bitv` items re-checked as merged. Sixth round 2026-11-17 at `f150f0d` (stabilisation of `main`, no features): new items
PROC-24 to PROC-27, CODE-58 to CODE-61, SEC-19, UX-44; SEC-15 fixed (see "Round of 2026-11-17" below). Seventh round 2026-11-19 (object interaction): UX-45 to UX-47, CODE-66 and CODE-67; second list of the same day, every open point of the branch: UX-48 to UX-53, CODE-68 to CODE-71, PROC-28 to PROC-33. Eighth round 2026-11-20 at `f34365f` (tracker update): ten items closed, UX-56 to UX-60 and PROC-40 added (see "Round of 2026-11-20"). Ninth round 2026-11-21 (the red CI after SEC-12): UX-56 to UX-58, UX-62, PROC-38, PROC-41 to PROC-43 fixed (see "Round of 2026-11-21" at the end).

## How to add a bug

Tell the QA role in chat: *title, what you saw, where*. It is entered here with the next ID, a category, a proposed
priority and a status. Every fix follows `CONTRIBUTING.md` rule 1: **the bug first gets a test that fails for the right
reason.** Where an item says "Acceptance", that is the test to write first.

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

### Open (85)

By priority (P1, P2, P3, then items that wait for a decision without one), then by ID.

| ID | Pri | Category | Title | Status | Opened | Fixed |
|---|---|---|---|---|---|---|
| WEB-01 | P1 | Website | The website describes features the product does not have | needs decision |  |  |
| SEC-06 | P2 | Security | The server's self-signed certificate is a CA with no name constraints | verified open |  |  |
| SEC-19 | P2 | Security / Perf | Imports run on the worker pool with no memory cap; `check_package` bounds the input, not the parsed model | **new, open** |  |  |
| SEC-22 | P2 | Security | Who wrote which stretch (`runs`, E9.10) is part of the content state, so a viewer still receives it: in the `blocks` method, in `text` events, in the snapshot and in her own sealed file, although D1261 says no data should be behind "show who wrote what" for a viewer | **new, open**, needs the owner's decision (mask it live and in the viewer's file, or accept it as content) |  |  |
| PERF-02 | P2 | Performance | Journal `fsync` on the event loop for every edit | verified open (2026-11-12; see CODE-13) |  |  |
| PERF-10 | P2 | Performance | What-if outcomes are recalculated on the event loop: 9 s per edit in a 1,000-cell model | **new, open** |  |  |
| UX-07 | P2 | UX / Web | Website blocks pinch-zoom (`user-scalable=no`) | open; the website is not in this repository (searched 2026-11-13) |  |  |
| UX-09 | P2 | UX | Six web menus against four in D4; the Linux shell maps between them | **new** |  |  |
| UX-21 | P2 | UX / AI | The chat promises `@ai` where no AI answers (creates), and the refusal names a missing switch | **new, open** |  |  |
| UX-22 | P2 | UX | The history speaks three dialects: one per app | **new, open** |  |  |
| UX-42 | P2 | UX / all | A document cannot be renamed: its name is sealed into the file, which the uid was meant to avoid | **decided, open** (D536, E5.21) |  |  |
| UX-51 | P2 | UX / composes | The words go round the unturned frame of a turned object, not its bounding box (D1226 decides the box); turning is on screen in composes since D1232 | **new, open** (read) |  |  |
| UX-68 | P2 | UX / computes | A sheet or a chart tab (after E6.31: a slide) cannot be deleted: nothing in the menus or the tab strip reaches `RemoveSheet` or `remove_chart` | **new, open** (read; size 2) | 2026-11-22 |  |
| CODE-25 | P2 | Code / Export | A renamed object loses its name in pptx and odp without the export saying so (D450) | **new, open** |  |  |
| CODE-31 | P2 | Code / i18n | The history speaks English to everybody: command labels and summaries are not translated | **new, open** |  |  |
| CODE-45 | P2 | Code / Import | pptx placeholders (titles, body text) are not imported at all | **new, open** |  |  |
| PROC-15 | P2 | Process | The tracker and the backlog lag the code: fixed items still "open", 64 stories at a placeholder 50 % | **new, partly fixed**; the tracker was brought up to date on 2026-11-20 (ten items closed, six added) |  |  |
| PROC-30 | P2 | Process / desktop clients | The Neutralino (Windows, macOS) tests and the GTK client were not run for `object-interaction`: the generated menus were rebuilt and the manifest unit tests pass, nothing more | **new, open** |  |  |
| PROC-37 | P2 | Process / scope | D1272 says an export's history and chat come back in with their authors as text; slice B imports the content only (`import_state` returns the state, the `history.jsonl` and `chat.jsonl` of an export are written but never read back) | **new, open** (size 2; needs the owner's decision: build it in slice C or log it) |  |  |
| PROC-40 | P2 | Process / E2E | Four spec files (51 scenarios) run nowhere: no step code binds them and no scenario names a unit or e2e test (`names`, `requirements`, `objects-in-composes`, `pictures-in-files`) | **new, open** (measured; size 2) | 2026-11-20 |  |
| SEC-09 | P3 | Security | User names can be confusable (homoglyphs) | open (unverified) |  |  |
| SEC-14 | P3 | Security / Privacy | `/api/swagger` loads its script from a CDN; the API description is public | **new, open** |  |  |
| SEC-16 | P3 | Security | The LaTeX program setting accepts any executable on the server | **new, open** |  |  |
| PERF-06 | P3 | Performance | Packing rewrites the whole zip; threshold packing on the event loop | verified open |  |  |
| PERF-07 | P3 | Performance | Structure edits recalculate the whole workbook (~12 s at 100k formulas) | verified open |  |  |
| PERF-08 | P3 | Performance | The first chart downloads all of Plotly (4.6 MB) for a bar chart | **new, open** |  |  |
| UX-08 | P3 | UX | Open and Create sit side by side; a typo cannot be told from a wrong password | open |  |  |
| UX-23 | P3 | UX | Panel layout and undo placement differ between the three apps | partly fixed 2026-11-12 (the suggestion list is gone from above the tabs) |  |  |
| UX-27 | P3 | UX / creates | A new object lands exactly on the previous one, so the second hides the first | **new, open** |  |  |
| UX-32 | P3 | UX / BITV | The workspace pages have no landmarks (axe `landmark-one-main`, `region`; WCAG 1.3.1, 2.4.1) | **new, open** |  |  |
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
| UX-54 | P3 | UX / a11y | The pages of Server settings (AI model … Security) have no keyboard shortcut, and the menu workbook does not list them | **new, open** (pre-existing; found while adding the Security page; needs the owner's decision whether the rule covers navigation) |  |  |
| UX-59 | P3 | UX / composes | Up from the second paragraph to the first failed once in four runs: a re-render of a paragraph just saved may undo a native caret move | **new, open** (measured once, cause a guess; size 3) | 2026-11-20 |  |
| UX-60 | P3 | UX / composes | Dragging an object to another paragraph is "Moved an object" in the history; the mock names the object and the paragraph | **new, open** (divergence from the mock of D1352; size 3) | 2026-11-20 |  |
| UX-63 | P3 | UX / all apps | The print preview says printing and saving a PDF are "recorded in the document's history"; they go into the exit record, which is not part of the history (glossary) | **new, open** (`web/app/components/PrintPreview.vue`, string in `po/`; size 3) | 2026-11-21 |  |
| UX-64 | P2 | UX / all apps | Dark mode: a part of the sidebar (History & Chat / Help) is not readable or has too little contrast; the exact symptom was not written down when it was seen (see entry) | **needs decision** (symptom to be re-stated; size 2) | 2026-11-22 |  |
| UX-65 | P3 | UX / composes | Search & replace panel, find-only state: the results list overflows its container and the "text" badge of a result is clipped at the panel edge | **new, open** (`web/app/components/SearchPanel.vue`; **measured** in the running app; size 3) | 2026-11-22 |  |
| UX-66 | P3 | UX / composes | `StylesDialog.vue` hard-codes `#7a4710` for the text of its `.flag` pill instead of a colour token (`--apricot-dark`), so it does not follow the themes | **new, open** (`web/app/components/StylesDialog.vue`; **read**; size 3) | 2026-11-22 |  |
| UX-67 | P3 | UX / a11y | The Heading and Numbering selects in the Styles dialog are unstyled native `<select>`s: they look unlike every other field and may diverge from BITV (focus, contrast, target size not tested) | **new, open** (`web/app/components/StyleSpec.vue`; **read**; size 3) | 2026-11-22 |  |
| CODE-03 | P3 | Code | README is out of date | open (not re-checked) |  |  |
| CODE-04 | P3 | Code | Untyped functions escape the type check | verified open |  |  |
| CODE-06 | P3 | Code | `--max-connections` is per document, not per server | open |  |  |
| CODE-17 | P3 | Code / tests | Three names for "use this browser" in the tests (`CHROME`, `CHROMIUM`, `CLAUDIA_CHROMIUM`) | **new, open** |  |  |
| CODE-19 | P3 | Code | A debugging scan of the garbage collector and a 10 s sleep loop left in the journal | **new, open** |  |  |
| CODE-20 | P3 | Code / Supply chain | The Dockerfile copies `uv:latest`: the image's build tool is not pinned | **new, open** |  |  |
| CODE-21 | P3 | Code | `claudia_server/computes.py` holds every computes method (1,228 lines) | open; search split out 2026-11-13; 1,121 lines at `7994b00` (see CODE-27, CODE-29) |  |  |
| CODE-28 | P3 | Code / Arch | An app's server wiring is spread over five tables in `apps.py` | **new, open** |  |  |
| CODE-29 | P3 | Code / Arch | `claudia_server` is flat: app glue next to infrastructure | **new, open** |  |  |
| CODE-30 | P3 | Code / server | Parameters are validated twice, and a handler's bug answers `command_error` | **new, open** |  |  |
| CODE-32 | P3 | Code / clients | The menu's one source lives inside the Linux shell, and the web menus are a second copy | **new, open** |  |  |
| CODE-35 | P3 | Code / web | The web sessions repeat their write call 57 times and three shared methods | **new, open** |  |  |
| CODE-36 | P3 | Code / web | `localStorage` is guarded six times over | **new, open** |  |  |
| CODE-37 | P3 | Code / web | Two image dialogs that differ in one prop | **new, open** |  |  |
| CODE-38 | P3 | Code / naming | computes kept the generic names (`Session`, `Workspace.vue`, `standin.py`) | **new, open** |  |  |
| CODE-39 | P3 | Code / web | `OpenDialog.vue` does five jobs in 1,615 lines | **new, open** |  |  |
| CODE-41 | P3 | Code / Arch | Import cycles in computes are worked around with 29 function-level imports | **new, open** |  |  |
| CODE-47 | P3 | Code / Import | Words of a docx with a font of their own are a `formatting` loss | **new, open** |  |  |
| CODE-53 | P3 | Web | The failure text of a rendered container is clipped in a small frame and cannot be read in full | open |  |  |
| CODE-54 | P3 | Code / Render | A finished picture is kept without the fonts in its key, so it stays after a font of the same family and style is replaced | open |  |  |
| CODE-56 | P3 | Code / computes | A new sheet can get the id of a removed sheet | **new, open** |  |  |
| CODE-62 | P3 | Code / Linux client | A window that revives the shared server while the old one still holds the port starts it on a random port, not the remembered one | **new, open** |  |  |
| CODE-63 | P3 | UX / composes | The Format ▸ Styles menu lists composes' built-in `contents-title` and `contents-1` to `contents-9` as "custom" styles | **new, open** (read) |  |  |
| CODE-66 | P3 | computes I/O | A picture added to an imported XLSX or ODS is not written into it: the patch of a kept file does not add pictures (reported as `object`) | **new, open** (D1233) |  |  |
| CODE-67 | P3 | computes I/O | Pictures of an XLSX or ODS are not read into the model: they stay in the file, are counted as `picture`, and survive an edit, but cannot be moved or described in computes | **new, open** (D1233) |  |  |
| CODE-68 | P3 | computes | Computes cannot make a text box or a shape, though a model can hold one (a file from another app) and an export reports it as `object` | **new, open** |  |  |
| CODE-69 | P3 | Code / shared objects | A shape's text is a plain `str`, not the shared paragraph entity: no styles, no authorship runs, no per-host overflow policy | **new, open** (implementation note, shared object layer) |  |  |
| CODE-70 | P3 | computes I/O | The patch of a kept XLSX or ODS does not add pivot tables either (reported), as it does not add pictures (CODE-66) | **new, open** (D1233) |  |  |
| CODE-71 | P3 | Code / web | `contextMenuItems` in `object-menu.ts` types four key hints by hand ("Enter", "Ctrl+X", "Ctrl+C", "Del"); the others come from the manifest through `hintOf` (see UX-47) | **new, open** (read) |  |  |
| CODE-74 | P3 | Code | `export_content` still answers `{format: "claudia-export 1", ...}`, a JSON that is neither the zip of D1270 nor documented anywhere; it is recorded as an export and the panel says "exported as claudia-export 1"; no window calls it | **new, open** (size 3; remove it or make it the zip) |  |  |
| CODE-75 | P3 | Code / web clients | Only composes refused a change of a viewer before sending it; computes sent it and showed the server's refusal, creates checked in some places only | **fixed** on `architecture-improvements` (D1432) | 2026-11-21 | 2026-11-21 |
| CODE-76 | P3 | Code / web clients | The sheet session ignored `shape` events, so an outline a colleague's sheet object needed arrived only with a reload | **fixed** on `architecture-improvements` (D1432) | 2026-11-21 | 2026-11-21 |
| PROC-22 | P3 | Process / CI | The LibreOffice job may still fail silently, though it has passed every round | **new, open** |  |  |
| PROC-29 | P3 | Process / E2E | No scenario asserts that a second window sees a holder's outline and name tag (D1223), nor that a colleague's drag is not shown live | **new, open** |  |  |
| PROC-31 | P3 | Process / i18n | `po/claudia.pot` goes stale at every merge of `main`: only its `#:` source lines move, no msgid changes, and the i18n check of `check_debt.py` fails on them | **new, open** (measured) |  |  |
| WEB-02 | P3 | Website | Download buttons are `#` placeholders | open |  |  |
| UX-06 | — | UX | Web menu differs from decisions D4/D5 | needs decision |  |  |

### Fixed (144)

By ID. Items closed without a fix (superseded, wontfix) are here too.

| ID | Pri | Category | Title | Status | Opened | Fixed |
|---|---|---|---|---|---|---|
| SEC-01 | P1 | Security | DNS rebinding defeats the Origin check | fixed (verified at `54d1245`) |  |  |
| SEC-02 | P2 | Security | Anyone who reaches the server can create unlimited documents | fixed (verified at `54d1245`) |  |  |
| SEC-03 | P2 | Security / Perf | Password hashing runs on the event loop | fixed (verified at `54d1245`) |  |  |
| SEC-04 | P2 | Security | Answer time reveals whether a document exists | fixed (verified at `54d1245`) |  |  |
| SEC-05 | P2 | Security | Redaction leaves the content in the journal and in packed blocks | **fixed** 2026-11-16 (D725) |  | 2026-11-16 |
| SEC-07 | P2 | Security | Plain-text passwords allowed on non-loopback addresses | fixed (verified at `54d1245`) |  |  |
| SEC-08 | P3 | Security | `npm audit` / `pip-audit` are not run by the gate or CI | **fixed** 2026-11-17 (npm audit 2026-11-11; `pip-audit` in CI since 2026-11-17, job `pip-audit`; clean when run by hand) |  | 2026-11-17 |
| SEC-10 | P2 | Security / Arch | The AI's method allow-list is enforced in the model parser, not at dispatch | fixed 2026-11-06 |  | 2026-11-06 |
| SEC-11 | P3 | Security | No per-address back-off on failed logins (now also the admin sign-in) | **fixed** 2026-11-19 (D1266, D1275, D1276; admin sign-in too; on `main` with `e2-document-sec` since 2026-11-20) |  | 2026-11-19 |
| SEC-12 | **P1** | Security | Anyone who reaches an exposed server with no administrator can become its administrator | **fixed** 2026-11-20 on `sec-12-setup-code` (D1370–D1376: every server asks for its setup code; the desktop apps hand it over; `--reset-administrators`, `--admin`) |  | 2026-11-20 |
| SEC-13 | P2 | Security | The web app is served without CSP, frame-ancestors, nosniff or referrer headers | **fixed** 2026-11-12 |  | 2026-11-12 |
| SEC-15 | P2 | Security | Office import reads every zip part whole and parses some XML with default parsers | **fixed** 2026-11-17 (`claudia_opc_io.check_package`, `parse_xml`) |  | 2026-11-17 |
| SEC-17 | P2 | Security | A viewer's connection receives the whole history and chat (E2.4), which the file itself withholds | open since 2026-11-05; **fixed** 2026-11-19 (D1261; on `main` with `e2-document-sec` since 2026-11-20); one part left, see SEC-22 | 2026-11-05 | 2026-11-19 |
| SEC-18 | **P1** | Security / Perf | A search pattern the static guard lets through freezes the whole server | **fixed** 2026-11-13 (D288) |  | 2026-11-13 |
| SEC-20 | P2 | Security | Behind `--behind-proxy` every client had the proxy's address, so the per-address caps (waiting sockets, lookups, uploads) were one cap for everybody | **fixed** 2026-11-19 (D1275, branch `e2-document-sec`) |  | 2026-11-19 |
| SEC-21 | P2 | Security / performance | Methods that confirm a password (`set_details`, `delete_document`, `leave`, `change_password`, `propose_owner`, `download_claudia`) hash on the event loop, in `Connection.handle`, not in a thread: at 0.75 s (D1267) each stops every connection of the server for that long | **fixed** 2026-11-19 on branch `e2-document-sec` (D1277) |  | 2026-11-19 |
| PERF-01 | P2 | Performance | `cells` window cost grows with the whole sheet | **fixed** (re-measured 2026-11-12) |  |  |
| PERF-03 | P3 | Performance | `users.json` rewritten and fsynced in full on every user added | superseded by the container |  |  |
| PERF-04 | P3 | Performance | `GET /api/docs` scans the disk on every request | fixed (listing cache) |  |  |
| PERF-05 | P2 | Performance | `sheets` recomputes the extent by scanning every cell | **fixed** (re-measured 2026-11-12) |  |  |
| PERF-09 | P2 | Performance | Making a webfont (WOFF2) blocked every request of every document for seconds | **fixed** 2026-11-13 |  | 2026-11-13 |
| PERF-11 | P3 | Performance | Search preview and replace have no time budget at all | **fixed** 2026-11-13 |  | 2026-11-13 |
| UX-01 | P2 | UX | Menus cannot be operated with the keyboard | fixed (read 2026-11-12, not screen-reader tested) |  |  |
| UX-02 | P2 | UX | The grid has no accessible structure | fixed, merged at `cfa2d91` (`grid-a11y.cjs` passes; no screen reader run yet) |  |  |
| UX-03 | P2 | UX | Dialogs do not manage focus | fixed (native `<dialog>`, read 2026-11-12) |  |  |
| UX-04 | P2 | UX | Text and border colours fail WCAG contrast | fixed, merged at `fd4b087` (guarded by a test) |  |  |
| UX-05 | P3 | UX | No dark mode | fixed (2026-11-12) |  | 2026-11-12 |
| UX-10 | P2 | UX / Web | An empty server greets everybody as computes, whichever app it serves | **fixed** |  |  |
| UX-11 | P2 | UX | The admin sign-in screen had no way back except the browser's Back button | **fixed** |  |  |
| UX-12 | P2 | UX | Open dialog goes blank if the server has an access secret | **fixed** |  |  |
| UX-13 | P2 | UX | `help_search` leaks one app's topics into another's; composes has none of its own | **fixed** |  |  |
| UX-14 | P2 | UX | "Edit this style…" gallery applies and closes on click instead of showing the style to inspect | **fixed** |  |  |
| UX-15 | P1 | IO / pptx | The PowerPoint exporter cannot be imported, and loses every colour when it can | **fixed** |  |  |
| UX-16 | P2 | UX / Web | A submenu opened by hovering closes again when its item is clicked (File ▸ Manage ▸ …) | **fixed** |  |  |
| UX-17 | P2 | UX / i18n | A browser in `en-US` asks for a catalog that does not exist; in `de-DE` it stays English with no language ticked | **fixed** |  |  |
| UX-18 | P2 | UX / computes | The formula hint covers the column letters exactly when a whole column is to be picked | **fixed** |  |  |
| UX-19 | P2 | UX | Picking the caret's own style back in the gallery pins it: a deviation is then not offered a name, and the next change goes to the old style everywhere | **fixed** |  |  |
| UX-20 | **P1** | UX / AI | The AI in computes does nothing and points at an act/suggest switch no client has | **fixed** 2026-11-12 |  | 2026-11-12 |
| UX-24 | P1 | UX / creates | A named style could not be applied to another text box from where people look for it | **fixed** 2026-11-12 |  | 2026-11-12 |
| UX-25 | P3 | UX / creates | All styles… counted every style's uses as "shapes" when a shape was selected | **fixed** 2026-11-12 |  | 2026-11-12 |
| UX-26 | P2 | UX | The AI mode switch: the unchosen half invisible in the light theme, and the switch below the history | **fixed** 2026-11-12 |  | 2026-11-12 |
| UX-28 | P2 | UX / BITV | The page declares no language (WCAG 3.1.1) | fixed, merged at `fd4b087` |  |  |
| UX-29 | P2 | UX / BITV | A keyboard user cannot leave the grid, nor skip the menus and toolbar (WCAG 2.1.2, 2.4.1) | fixed, merged at `fd4b087` (`regions.cjs` passes) |  |  |
| UX-30 | P3 | UX / BITV | The tab title does not name the document (WCAG 2.4.2) | fixed, merged at `fd4b087` |  |  |
| UX-31 | P2 | UX / BITV | Pictures, charts and shapes had no description of their own, and nothing could be marked as decoration (WCAG 1.1.1) | fixed, merged at `cfa2d91` (`describe*.cjs` pass); design to confirm |  |  |
| UX-33 | P2 | UX | A new document starts with an undoable step: Ctrl+Z removes a new workbook's only sheet | **fixed** 2026-11-13 (D362) |  | 2026-11-13 |
| UX-35 | P2 | UX | 30–37 menu entries per app have no shortcut; the native menu hides the ones the page handles | **fixed** 2026-11-13 (D360) |  | 2026-11-13 |
| UX-36 | P2 | UX / desktop | Features of this round are missing from the native desktop menus (Print, lists, Image, Chart, Names, SQL, …) | **fixed** 2026-11-13 (D361) |  | 2026-11-13 |
| UX-37 | P3 | UX / composes | composes shows an act/suggest switch that changes nothing | **fixed** 2026-11-16 (composes has its AI, D640, D681: *suggest* and *act* differ there now) |  | 2026-11-16 |
| UX-38 | P2 | UX / Linux client | Dialogs are stretched to the window's height in WebKitGTK: huge gaps, a button in a row of its own turns into a circle | **fixed** 2026-11-14 (`web/tests/modal-layout.test.ts`) |  | 2026-11-14 |
| UX-39 | P2 | UX | A dialog or the search panel cannot be moved; its help link did not reach its topic; help topics showed their Markdown as typed | **fixed** 2026-11-15 (D520–D522) |  | 2026-11-15 |
| UX-40 | P2 | UX / creates | A new presentation's first slide had no name; the next one was called "Slide 1" too, and both tabs said "Slide 1" | **fixed** 2026-11-15 |  | 2026-11-15 |
| UX-41 | P2 | UX / composes | Headings, list items and paragraphs could not be pointed at with `#` in the chat | **fixed** 2026-11-15 (D554) |  | 2026-11-15 |
| UX-44 | P3 | UX / BITV | The blinking dots of the side panel ignored `prefers-reduced-motion` (WCAG 2.3.3) | **fixed** 2026-11-17 |  | 2026-11-17 |
| UX-55 | P2 | UX / record | After its own export, print or PDF the window that did it was not shown its own line in History & Chat: the server tells the other windows only | **fixed** 2026-11-19 in slice B (found by the first end-to-end run; `BaseSession.recorded` reads the record again) |  | 2026-11-19 |
| UX-56 | P2 | UX / creates | Enter in the Rotate by… field is taken by the slide: it starts writing in the selected text box, and the angle is not applied | **fixed** 2026-11-21 (the grid and the slide leave the keys of a dialog inside them to the dialog; `objects.cjs` checks Enter and Backspace; size 2) | 2026-11-20 | 2026-11-21 |
| UX-57 | P2 | UX / computes | Turning a picture by its turn handle did not happen: the press on a handle also reached the cell selection and let go of the picture | **fixed** 2026-11-21 (`objects.cjs` step 5; size 2) | 2026-11-20 | 2026-11-21 |
| UX-58 | P3 | UX / composes | A press on a text box also moved the caret in the words below it | **fixed** 2026-11-21 (`objects.cjs` step 1; size 3) | 2026-11-20 | 2026-11-21 |
| UX-61 | P3 | UX / admin | The first-administrator page and Access & documents called the access secret a recovery key for administrators: there is no such recovery, and nobody signs in with it | **fixed** 2026-11-20 (`web/tests/admin-wording.test.ts`; size 3) | 2026-11-20 | 2026-11-20 |
| UX-62 | P3 | UX / composes | ← and → did nothing on a selected object, where the contract says the arrow keys nudge it | **fixed** 2026-11-21 (D1390; `objects.cjs` step 6; size 3) | 2026-11-21 | 2026-11-21 |
| CODE-01 | P2 | Code | No coverage, no web lint; Playwright not declared | **fixed** |  |  |
| CODE-02 | P3 | Code | 26 build files tracked in `web/dist` | fixed |  |  |
| CODE-05 | P3 | Code | Dead branch in `Gateway.admit`; stale docstring in `state.py` | **fixed** (the branch was not dead: comment corrected) |  |  |
| CODE-07 | P3 | Code | `uv.lock.rej` committed at the repository root | fixed |  |  |
| CODE-08 | P3 | Code | `ruff format --check` fails; the gate does not run it | fixed |  |  |
| CODE-09 | P3 | Code | e2e scripts exist without `package.json` entries | fixed |  |  |
| CODE-10 | P1 | Code | `main` at `558f429` has a real `SyntaxError` in 10 files: `except A, B:` instead of `except (A, B):` | fixed |  |  |
| CODE-11 | P3 | Code | Windows client: its generated menu is stale, and a test depends on the clone's folder name | **fixed** |  |  |
| CODE-12 | P3 | Code | `.gitignore` ignores the tracked `docs/` sources; two test documents are committed | **fixed** |  |  |
| CODE-13 | P2 | Code / Perf | `WorkerPool` is built and owned by every hub, and nothing submits work to it | **fixed** 2026-11-19: imports run on the pool, heavy formula calls are sent to it (D1314); the what-if outcomes are not (PERF-10) |  | 2026-11-19 |
| CODE-14 | P2 | Code / Arch | The Windows and macOS shells are one design kept as two copies (~1,550 identical lines) | **fixed** 2026-11-15 (D660) |  | 2026-11-15 |
| CODE-15 | P2 | Code | `./start.sh` kept documents in three layouts and all servers' state in one shared folder | **fixed** 2026-11-12 |  | 2026-11-12 |
| CODE-16 | P2 | Code / macOS | The macOS client's generated creates menu had no Format ▸ Apply Style…, and nothing checked it | **fixed** 2026-11-12 |  | 2026-11-12 |
| CODE-18 | P2 | Code / Arch | The search panel and protocol "for all three apps" speak only in sheet, row and column | **fixed** 2026-11-13 (D289) |  | 2026-11-13 |
| CODE-22 | P2 | Code / Import | An xlsx with an array formula failed to import; one edit dropped a sheet's lists, icon sets and spill marks | **fixed** 2026-11-13 |  | 2026-11-13 |
| CODE-23 | P2 | Code / clients | The Windows and macOS menus lacked Insert ▸ Container: their generated menus were stale and CI's client job red (CODE-16 again) | **fixed** 2026-11-15 |  | 2026-11-15 |
| CODE-24 | P3 | Code / server | `add_object` with kind `rendered` or `diagram` failed inside the server after a message that allowed them | **fixed** 2026-11-15 |  | 2026-11-15 |
| CODE-26 | **P1** | Code / macOS client | Closing a window with its close button crashes the macOS app every time (Neutralino 6.8.0) | **fixed** 2026-11-15 (D506) |  | 2026-11-15 |
| CODE-27 | P2 | Code / Arch | The object methods are written once in the kernel and three times on the wire | **fixed** 2026-11-19: the server's methods 2026-11-15; composes' Edit ▸ Image… and Format ▸ Name & describe… (D1317) followed; the web sessions' copies are CODE-35 |  | 2026-11-19 |
| CODE-33 | P3 | Code | `claudia-client` is a package no client uses | **fixed** 2026-11-16 (D700) |  | 2026-11-16 |
| CODE-34 | P3 | Code / Windows | Atomic writes are written seven times; five lack the Windows retry | **fixed** 2026-11-16 (D701) |  | 2026-11-16 |
| CODE-40 | P3 | Code / macOS client | An orphaned build file in the macOS creates app | **fixed** 2026-11-15 (with D660) |  | 2026-11-15 |
| CODE-42 | P3 | Code / Export | Exports named a generic font family by a font Claudia does not show | **fixed** 2026-11-16 (E3.13) |  | 2026-11-16 |
| CODE-43 | P2 | Code / Import | docx and odt import ignored the file's fonts and reported no loss | **fixed** 2026-11-16 (E3.13) |  | 2026-11-16 |
| CODE-44 | P2 | Code / Import | pptx and odp import did not read fonts | **fixed** 2026-11-16 (E3.13) |  | 2026-11-16 |
| CODE-46 | P2 | Code / Import | The slides importers do not read text size and colour, so most boxes are a `look` loss | **fixed** 2026-11-17 (IEW-20, D467: `_pptx_looks` and `_odp_looks` read a box's size and colour) |  | 2026-11-17 |
| CODE-48 | P3 | Code / Web | After naming the first administrator, the server settings stayed on the setup form | **fixed** 2026-11-17 |  | 2026-11-17 |
| CODE-49 | P2 | Code / Server | Add fonts… stayed blocked for 30 minutes after too many files were chosen | **fixed** 2026-11-17 |  | 2026-11-17 |
| CODE-50 | P2 | Code / Render | LaTeX formulas ignored fonts added while the server ran ("Latin Modern Roman is not available") | **fixed** 2026-11-17 |  | 2026-11-17 |
| CODE-51 | P2 | Code / Server | A container whose picture was never made stayed on "Drawing…" for ever, also after reopening the document | **fixed** 2026-11-17 |  | 2026-11-17 |
| CODE-52 | P3 | Code / Typeset | A TeX error was cut at 79 characters ("Fatal Package", "cannot be f") | **fixed** 2026-11-17 |  | 2026-11-17 |
| CODE-55 | P2 | Code / Server | A tool path changed in Server settings (xelatex, pdftocairo) was used only after a restart of the server | **fixed** 2026-11-17 |  | 2026-11-17 |
| CODE-57 | P2 | Code / core | Undoing typing after an undone delete that cut into it removes the wrong characters | **fixed** 2026-11-17 |  | 2026-11-17 |
| CODE-58 | P2 | Code / Export | pptx and odp exports drop border, padding, line-height, letter-spacing, hyphenation and margins of creates text styles and report no loss | **fixed** 2026-11-17 (D760: reported, not yet written) |  | 2026-11-17 |
| CODE-59 | P3 | Code / Drift | `OBJECT_KINDS` was written in `claudia_core` and again in `claudia_computes.model` | **fixed** 2026-11-17 |  | 2026-11-17 |
| CODE-60 | P2 | Code / Drift | Facts written twice: the web's built-in style ids and `'body-text'` literals, `VisualObject.kind` in `layout/` lacks `rendered`, list leader dots drawn differently by the editor and the display list | **fixed** 2026-11-17 (D761); see CODE-63 |  | 2026-11-17 |
| CODE-61 | P3 | Process / Backlog | Stale statuses in the backlog (E9.30, E10.21, probably E9.31 say open where code exists) | **fixed** (seen 2026-11-20: E9.30 and E9.31 are `done`, E10.21 is `in-progress`) |  |  |
| CODE-64 | P2 | composes | The browser editor does not draw the text wrap (the flowing view shows objects over the words; Page view and print wrap) | **fixed** 2026-11-18 (D1068) |  | 2026-11-18 |
| CODE-65 | P2 | composes I/O | `dx`/`dy` of an object is not written to or read from DOCX/ODT | **fixed** 2026-11-18 (D1067) |  | 2026-11-18 |
| CODE-72 | P3 | Code / docs | `KdfParams`' docstring said that the cost can be raised "at the next login"; it cannot for a document with several people | **fixed** 2026-11-19 |  | 2026-11-19 |
| CODE-73 | P2 | Code / security | File ▸ Download wrote the unencrypted content-only JSON while D110 and the menu workbook say it is the sealed file | **fixed** 2026-11-19 (D1270, E2.12) |  | 2026-11-19 |
| PROC-01 | P1 | Process | No CI workflow in the repository | fixed (verified at `54d1245`) |  |  |
| PROC-02 | P2 | Process | The quality gate prints "everything is clean" when half of it was skipped | fixed |  |  |
| PROC-03 | P2 | Process | Work described as delivered is not in the repository | fixed |  |  |
| PROC-04 | P1 | Process / CI | CI's Python job fails on every OS: "e2e greeting" skips and `--ci` does not allow it | **fixed** |  |  |
| PROC-05 | P2 | Process / CI | CI's web type check checks nothing (`vue-tsc --noEmit` over a `files: []` tsconfig) | **fixed** |  |  |
| PROC-06 | P2 | Process / CI | No CI job runs a browser or the Windows client; the `web/e2e` scripts had rotted unnoticed | **fixed** |  |  |
| PROC-07 | P3 | Process / tests | A performance guard measures the garbage collector and fails now and then | **fixed** |  |  |
| PROC-08 | P3 | Process / tests | A test of the gate fails on every machine where `npm install` has been run | **fixed** |  |  |
| PROC-09 | P1 | Process / CI | Two branches both released claudia-core 0.13.0; the gate fails on the duplicate | **fixed** 2026-11-12 |  | 2026-11-12 |
| PROC-10 | P1 | Process / CI | The Sphinx build fails: `Budget`, `Lens`, `Recorder` are in signatures but not in the reference | **fixed** 2026-11-12 |  | 2026-11-12 |
| PROC-11 | P2 | Process / CI | The LibreOffice check broke silently: its job may fail and nothing else runs its code | **fixed** 2026-11-12 |  | 2026-11-12 |
| PROC-12 | P1 | Process / CI | The Linux client's end-to-end test reads the page address before the page starts loading | **fixed** 2026-11-12 |  | 2026-11-12 |
| PROC-13 | P2 | Process | Nothing pins Python 3.14: `uv` takes 3.15 where it is installed, and OpenVINO cannot be installed there | **fixed** 2026-11-12 |  | 2026-11-12 |
| PROC-14 | P2 | Process / CI | Two web browser scripts fail on `main` (a stale selector, and UX-20) | **fixed** 2026-11-12 |  | 2026-11-12 |
| PROC-16 | P3 | Process / tests | The undo performance guard measured one sample and failed now and then | **fixed** 2026-11-12 |  | 2026-11-12 |
| PROC-17 | P2 | Process / CI | `web/e2e/demo.cjs` fails again once the client sends *suggest*: it never switched to *act* | **fixed** 2026-11-12 |  | 2026-11-12 |
| PROC-18 | **P1** | Process / CI | The gate fails on every fresh clone: a note names `web/public/wasm`, a build output | **fixed** 2026-11-13 |  | 2026-11-13 |
| PROC-19 | P2 | Process / CI | Six browser scripts and the macOS client's own tests ran nowhere; image and .deb ignored `layout/` | **fixed** 2026-11-13 |  | 2026-11-13 |
| PROC-20 | **P1** | Process / CI | Two end-to-end tests on `main` fail: `demo.cjs` (the grid's blank active cell) and the Linux client (D915) | **fixed** 2026-11-13 |  | 2026-11-13 |
| PROC-21 | P2 | Process / CD | The demo deployment checks `demo.claudiaoffice.de`, a domain that is not ours | **fixed** 2026-11-13 |  | 2026-11-13 |
| PROC-23 | **P1** | Process / CI | Three web e2e scripts on `main` fail after the dock merge (`demo`, `composes`: the chat box; `keys`: the View menu); `details.cjs` never ran in CI | **fixed** 2026-11-15 |  | 2026-11-15 |
| PROC-24 | **P1** | Process / CI | `main` after the last merge was red: two tests (a story id and decision numbers D730–D735 used twice) | **fixed** 2026-11-17 |  | 2026-11-17 |
| PROC-25 | P2 | Process / CD | The demo deployment was not gated on CI: it deployed whatever an image push produced, also from a red `main` | **fixed** 2026-11-17 |  | 2026-11-17 |
| PROC-26 | P3 | Process / Supply chain | No dependabot: five lockfiles and the workflows were never watched | **fixed** 2026-11-17 |  | 2026-11-17 |
| PROC-27 | P2 | Process / Supply chain | Actions are pinned by tag, not SHA; the `latest` image tag follows a red `main`; CI has no CodeQL and no `pip-audit` | **fixed** 2026-11-17 (D762); first runs unseen |  | 2026-11-17 |
| PROC-28 | P2 | Process / E2E | `web/e2e/objects.cjs` (D1231) was written and never run: the sandbox had no browser. Its first run is the proof of D1221–D1232 on screen | **fixed** 2026-11-20: first run on `fix-table-exit-object-sizes`; its red steps are app bugs, UX-56 to UX-58 |  | 2026-11-20 |
| PROC-32 | P3 | Process / docs | `claudiaoffice-log/notes/claudia-menus.xlsx` is not in the repo: the keys of this round are only in the generated key table, and the rows the contract note lists "for the workbook" are not settled | **fixed** 2026-11-19 (in the repo since `496b3db`; the keys of the later rounds are in it) |  | 2026-11-19 |
| PROC-33 | P3 | Process / gate | Patches 9–11 had ruff failures (lines over 120 characters in three files) that only the gate on the merged tree found | **fixed** 2026-11-19 (patch 12) |  | 2026-11-19 |
| PROC-34 | P3 | Process / backlog | The `backlog` branch had renamed `e0.3-shells-gtk-with-webkitgtk-6-0.md` (an Obsidian plugin does that when a title changes) so the story and its epic no longer named each other and `tests/test_backlog.py` failed | **fixed** 2026-11-19 (file name restored) |  | 2026-11-19 |
| PROC-35 | P3 | Process / e2e | `uv run pytest tests/e2e` as one run fails three tests ("Playwright Sync API inside the asyncio loop") that each pass alone: an earlier test leaves an event loop running | **fixed** 2026-11-19 on branch `e2-document-sec` (measured on the branch, which has no change to the other e2e tests) |  | 2026-11-19 |
| PROC-36 | P3 | Process / tooling | A `ruff` installed outside the project (0.16.9) rewrites `except (A, B):` into `except A, B:` and reformats unrelated files; the project pins `ruff<0.15` for this | **fixed** 2026-11-19 (a rule in `CONTRIBUTING.md`, rule 5) |  | 2026-11-19 |
| PROC-38 | P3 | Process / tests | `test_another_window_is_answered_quickly_while_a_password_is_hashed` assumed that hashing takes more than 0.15 s: on the CI runners it took 0.12 s and the test failed on all three systems | **fixed** 2026-11-21 (the test measures this machine and takes as many passes as it needs; size 3) |  | 2026-11-21 |
| PROC-39 | P2 | Process / e2e | The test server's output went to a pipe nobody read (`tests/e2e/live.py`); after about 64 KiB the server blocked on its next write and the whole event loop stood still, so page loads timed out (three `test_viewer` scenarios failed in a full run of `tests/e2e/specs` and passed alone) | **fixed** 2026-11-19 on branch `e2-document-sec` (the output goes to `server.log`; `test_greeting.py` and `test_computes_grid.py` still use a pipe but stop their servers within a minute) |  | 2026-11-19 |
| PROC-41 | P3 | Process / E2E | `test_computes_grid.py` stopped its launcher but not the server the launcher had started, which lived on after the run | **fixed** 2026-11-21 (the whole process group is stopped; size 3) | 2026-11-21 | 2026-11-21 |
| PROC-42 | P2 | Process / CI | The CI step "Server settings ▸ Fonts" did not give `e2e:admin-fonts` the setup code that SEC-12 made necessary: it would have been the next red step | **fixed** 2026-11-21 (the step reads the code from the state folder; size 2) | 2026-11-21 | 2026-11-21 |
| PROC-43 | P2 | Process / E2E | The job "End to end (Chromium)" was red from 2026-11-17: each first failure hid the next, and four lines of `objects.cjs` were stale (proportions of a free rectangle, the name of a table's menu, "Edit text" for a picture in creates, a race on the history entry of Delete) | **fixed** 2026-11-21 (the script follows the contract; it ran six times in a row; size 2) | 2026-11-21 | 2026-11-21 |
| PROC-44 | P3 | Process / CI | Two timing flakes on shared runners: `test_the_anchor_is_shown_when_the_object_is_selected` (setup clicked before the layout settled; fixed with `settled_box`) and `test_calculating_a_long_chain_is_linear` (one run 44x instead of ~10x, green on rerun; **open**, the retry in the test is too thin) | anchor spec **fixed** 2026-11-21; perf test **open** (size 3) | 2026-11-21 | |
| PROC-45 | P2 | Process / CI | The Linux client's end-to-end test still looked for `[data-block]` after the paragraph rename of E1.18 made it `data-paragraph`, so the job "Linux client" was red on `main` | **fixed** 2026-11-22 (size 3) | 2026-11-22 | 2026-11-22 |
| DOC-01 | P2 | Docs | Decision numbers D70–D82 and D97–D99 are used twice for different decisions | fixed |  |  |
| DOC-02 | P3 | Docs | `start-client.sh` was renamed; the Linux README and the other launchers still named it | **fixed** 2026-11-13 |  | 2026-11-13 |
| DOC-03 | P3 | Docs | Current decisions that later ones contradict (D2, D44, D84, D115, D242); a stale row in `ranges.md`; stale lines in two notes | **fixed** 2026-11-17 (log audit: D44, D84, D115 superseded; D2, D242 noted) |  | 2026-11-17 |
| DOC-04 | P3 | Docs | `docs/versioning.md` said the protocol version is "now 1"; the code says 2 | **fixed** 2026-11-19, with a test that compares them |  | 2026-11-19 |
| DOC-05 | P3 | Docs | The docs build of the gate failed: Sphinx could not resolve `T` and `asset_store.Asset` in `AssetStore[T: Asset]` | **fixed** on `architecture-improvements` | 2026-11-21 | 2026-11-21 |

---

## Security

### SEC-01 · DNS rebinding defeats the Origin check · P1 · fixed
Fixed in claudia-server 0.6.0: `HostGuard` (`hosts.py`) as the outermost ASGI layer, a Host allow-list, 403 / close
4403, `--allow-host`. Verified at `54d1245`: `app.py` adds `HostGuard` last so it sees a request first, and
`test_server_hosts.py` covers it. Details: `notes/e3-server-and-security.md`.

### SEC-02 · Anyone who reaches the server can create unlimited documents · P2 · fixed
Fixed in 0.6.0: `--max-documents` (1000), `--max-waiting` (256), `--max-waiting-per-address` (64), optional access
secret. Verified at `54d1245`: `_Waiting` in `app.py`, `hub.ensure_room()`, `Gateway.accepts_secret`.

### SEC-03 · Password hashing runs on the event loop · P2 · fixed
Verified at `54d1245`: `Gateway._verify` runs `directory.verify` through `asyncio.to_thread` behind a
`max_hashing` semaphore. Note the interaction found while building the container: OpenSSL's multi-lane Argon2id is
serialised by a process-wide lock, so the effective concurrency is 1 at the default parameters. That is a throughput
limit (2.5–5 logins per second), not a correctness problem, and it is the reason the KDF calibration question matters.

### SEC-04 · Answer time reveals whether a document exists · P2 · fixed
Verified at `54d1245`: `Gateway._admit` runs the same `_verify` on the not-found path before refusing. The guarding
test is a timing comparison and is known to be flaky on a loaded machine; see PROC note in CODE-01.

### SEC-05 · Redaction leaves the content in the journal and in packed blocks · P2 · fixed 2026-11-16
**Evidence (read, `54d1245`).** `claudia_container.container` has no `redact`. The journal is append-only and packing
writes blocks; neither rewrites history to remove a redacted command. The kernel's `Document.redact` changes the live
state and the log it replays, but the bytes stay in the file.
**Why it matters.** Redaction is a stated product promise (D21, E1.8 "done (draft)") and the container is now the real
store, so this is no longer only about a demo journal. Not reachable on the wire today (no `redact` method), so P2; it
becomes P1 the day redaction is exposed or the website's privacy claim (WEB-01) is kept.
**Fix.** The atomic rewrite named in the E2 design: on redaction rewrite the affected blocks and the journal (temp
file, fsync, rename, directory fsync), drop the snapshot, rebuild. Also state plainly in the help text that copies and
backups made earlier keep the content.
**Acceptance.** After `redact`, a byte scan of every file under the document folder finds none of the redacted text.
**Fixed (2026-11-16, branch `redaction`, D725).** `Document.redact` calls `DocumentStore.rewrite(log, chat)` instead of
appending a `replace` record. The sealed store seals the blocks anew from the redacted history and chat alone, drops the
snapshot and replaces the journal (`claudia_container.rewrite_journal`, same crash order as packing); a redacted import
also loses its kept original (`forget_original`). The plain journal store writes its journal anew, all at once. Tests
open every block, the snapshot and every journal record with the keys and find nothing of the redacted content, also
after a crash between the file and the journal (`packages/claudia-container/tests/test_rewriting.py`,
`packages/claudia-server/tests/test_server_redaction_stores.py`). Still true and now said in D725: copies and backups
made earlier keep the content, and what a disk keeps of overwritten sectors is outside Claudia's reach.

### SEC-06 · The server's self-signed certificate is a CA with no name constraints · P2 · verified open
**Evidence (read, `54d1245`).** `certs.py` line 100: `BasicConstraints(ca=True, path_length=0)`, critical, with
`key_cert_sign=True`. The private key sits on the server's disk.
**Why it matters.** If a person installs it into the system trust store (which "trust this certificate" instructions
invite), whoever steals the key file can sign certificates for *any* site for that person.
**Fix.** Prefer `ca=False` plus partial-chain verification in the clients that pin a certificate (since D700 the Linux
shell's `trust.py`; `claudia_client` is gone), or add a critical
`NameConstraints` extension limited to the certificate's own names.
**Acceptance.** The client still connects with fingerprint pinning; `openssl verify` of a certificate for another name
signed by the same key fails.

### SEC-07 · Plain-text passwords on non-loopback addresses · P2 · fixed
Verified at `54d1245`: `--no-tls` with a non-loopback `--host` raises `UsageError` unless `--behind-proxy`.

### SEC-08 · Dependency audits are not run by the gate or CI · P3 · fixed 2026-11-17
**Update 2026-11-11.** The npm half is done: `scripts/check_npm_audit.py` is a step of the gate (so also of CI, on every
push and weekly) and audits every `package-lock.json`, development tools included, failing on moderate or worse; the
allow-list is `[[tool.claudia.npm-audit-allow]]` in `pyproject.toml` (empty; a reason is required, an unneeded entry
fails). The findings that had piled up were fixed first (`implementation-notes/implementation-notes-npm-audit-2026-11-11.md`).
Open: the same for the Python dependencies (`pip-audit` or `uv pip audit` against `uv.lock`).
**Evidence (read, `54d1245`).** `scripts/check_debt.py` runs ruff, mypy, vulture, pytest, Sphinx, perf guards and the
web checks. It runs no `npm audit`, no `pip-audit`. `.github/workflows/ci.yml` adds none either.
**Fix.** Add `npm audit --omit=dev` and `pip-audit` (or `uv pip audit`) to the gate, with an allow-list that needs a
written reason per entry.
**Acceptance.** The gate fails on a new high or critical advisory.
**Re-checked 2026-11-20 at `f34365f`.** Both audits run: `scripts/check_npm_audit.py` in the gate and CI, `pip-audit` as
its own CI job.

### SEC-09 · User names can be confusable · P3 · unverified
**Evidence (read).** `claudia_container.crypto._normalise_name` uses NFKC and `casefold`, which does not fold Cyrillic
`а` to Latin `a`. Only an owner adds users, so the risk is an owner impersonating a colleague in the history.
**Fix.** Reject mixed-script names, or mark two confusable names in one document. Verify with a two-user test first.

### SEC-10 · The AI's method allow-list is enforced in the model parser, not at dispatch · P2 · fixed 2026-11-06
**Evidence (measured, `54d1245`), before the fix.**
- `apps.MODEL_METHODS` is `{"computes": ("set_cells", "add_sheet", "structure")}`. It decides which `ToolSpec`s are
  *described to the model in the prompt*.
- `claudia_ai.agent.Agent._take_calls` drops a request whose name is not in that set. This is a filter on the model's
  generated text, inside the AI library.
- `Assistant._call` (`assistant.py`) calls `hosted.methods.dispatch(context, method, params)` with **no allow-list**. A
  check for `MODEL_METHODS` in its source: absent.
- `protocol.py` contains **zero** `account.system` checks. The generic write method `apply` decodes any command and
  executes it as the calling account.
- `composes.py` has two `account.system` checks (`_people_only` guards `replace_text` and `set_style`; `suggest` is
  assistant-only) — but `apply` is inherited from `core_methods` and bypasses both.
- Write methods reachable at dispatch that the model is never offered: core `apply`, `chat`, `lock`, `redo`,
  `save_checkpoint`, `undo`, `unlock`; composes adds `replace_text`, `set_style`, `accept_suggestion`, and the style
  methods. `MODEL_METHODS` has no entry for composes at all, so a composes assistant is offered nothing — and is
  stopped only because `Agent` finds an empty allowed set.
**Why it matters.** Two product rules depend on this boundary: D63 ("edits by the AI are suggestions; people write")
and E7.6 ("a guarantee that the AI cannot add functions"). Both were enforced by a regex-extracted JSON block filtered
against a name set in a client library, not by the server's authorisation layer where the account is known. Nothing
was remotely exploitable, since every engine in the tree is trusted in-process code, but it becomes serious at two
named milestones — E7.5, which puts document content into the prompt (prompt injection from a cell then chooses method
names), and E3.6/D8, which moves the engine to another machine behind a socket.
**Fix, applied in claudia-server 0.9.0.** `Account.allowed_methods` (`auth.py`): the write methods an account may
call, `None` for an ordinary person. `MethodTable.dispatch` (`protocol.py`) refuses a write method outside it with
`forbidden`, before the method runs — the one place every path goes through: `Assistant._call`, the wire, and any
future remote AI connection. `protocol._apply` separately refuses `account.system` unconditionally, so `apply` cannot
be used as a tunnel around an app's own wrapper checks whatever the allow-list says. `Assistant(allowed_methods=...)`
passes the set on when its account is made; `apps.stand_in_assistant_for` and `apps.model_assistant_for` both set it
from `apps.MODEL_METHODS`, so the scripted stand-in is held to the same guarantee as a real model. `MODEL_METHODS`
gained a `"composes"` entry (`("suggest",)`). `Agent._take_calls` is unchanged: it stays a friendly early message to
the model, not the thing the guarantee rests on.
**Verification.** `test_server_protocol.py` (the mechanism directly: a restricted account may call what is in its
list and nothing else, reading is unaffected, `apply` refuses `account.system` even when `apply` is itself allowed);
`test_server_assistant.py` (end to end, with a rogue engine: `apply`, `chat`, `undo` and `save_checkpoint` are all
refused and change nothing; a composes assistant may `suggest` and nothing else); `test_server_auth.py` and
`test_server_standin_text.py` updated for the new, explicit allow-lists. Full suite green; `uv run python
scripts/check_debt.py --fast` clean (ruff, mypy, vulture, docs, tests) except a pre-existing, unrelated `mypy` failure
in the Linux client (`clients/linux/tests/test_manifest.py`, a `Submenu` union-attr error) — not touched by this fix
and not re-checked here. Not yet re-verified against a commit hash: this round's patch has not been merged.

### SEC-11 · No per-address back-off on failed logins · P3 · fixed 2026-11-19
**Fixed (D1266, D1276).** `LoginThrottle` before any hashing, at the document's `hello`, the recovery and the administrator's sign-in; code 4429 / 429 with `retry_after`; the web app counts down. In memory by decision (D1276): a restart forgets it.

**Evidence (read).** `_Waiting` bounds how many connections wait to be let in, but nothing slows a patient guesser who
logs in once, fails, disconnects and repeats. Named as the remaining part of E2.7 in the security-fix notes.
**Fix.** Per-address and per-(document, name) back-off with a cap, on top of the hashing semaphore.

---
**Re-checked 2026-11-12:** still no back-off, and the new administrator sign-in (`POST /api/admin/login`) has none
either; with SEC-12 fixed it becomes the way in, so it needs the same per-address back-off as documents.
**Re-checked 2026-11-20 at `f34365f`.** `e2-document-sec` was merged into `main` on 2026-11-20 (`1d8415a`);
`login_throttle.py` guards the document logins and `admin_api.py` `login` the admin sign-in (429 with `Retry-After`).

### SEC-12 · Anyone who reaches an exposed server with no administrator can become its administrator · P1 · fixed 2026-11-20
**Evidence (measured, `7e619a2`).** `admin_api.py` `setup` needs nothing but a name and a password while
`len(context.admins) == 0`. A server bound beyond loopback (`exposed`: every Docker container, the Scaleway demo) asks
for its first administrator, and the first anonymous visitor wins. Reproduced with
`CLAUDIA_ACCESS_SECRET=… python -m claudia_server --host 0.0.0.0 --no-tls --behind-proxy`: `POST /api/admin/setup`
answered 200 with a session; the access secret is not asked for. As that administrator one can then remove the
access secret (`PUT /settings/access-secret` `null` replaces even the one from the environment), point the AI at any
folder on the machine (`PUT /settings/ai`) and name any executable as `xelatex` (SEC-16). On a platform without a
persistent `/data/state` (the serverless demo) the window opens again on every cold start.
**Fix (not built: recommendation, agreed 2026-11-12).** The usual bootstrap: at start, an exposed server with no
administrator makes a one-time setup code, prints it in its banner and log only (never over HTTP), and `setup`
requires it (constant-time compare; the code dies with the first administrator or at restart). When an access secret
is set, `setup` also requires it. `FirstAdminSetup.vue` gets one field, "Setup code (printed in the server's log)",
mock-up first. Optional: `--admin NAME` / `CLAUDIA_ADMIN_PASSWORD_FILE` to make the first administrator at start, for
deployments. Until then: on the demo, sign up the administrator right after every deploy, or block `/api/admin/` at
the proxy.
**Acceptance.** `test_admin_api`: on an exposed server `setup` without the code → 403, with a wrong code → 403 and the
same time as a right one, with the code → 200 once; with an access secret, the code alone → 403. The banner test shows
the code exactly once.
**Agreed 2026-11-20 (D1370–D1376), replacing the recommendation above:** every server asks for the code, loopback
included (the desktop apps hand it over); the code alone is enough, also with an access secret; a server behind a proxy
counts as exposed; `--reset-administrators` and `--admin` with a password file are in scope. Branch `sec-12-setup-code`;
scenarios in `specs/server/administrators.feature`.
**Fixed 2026-11-20** on `sec-12-setup-code`: `setup_code.py`, `admin_start.py`, the admin API and `cli.py`; the setup
page, the sign-in and Access & documents; `welcome.setup_code` in both desktop apps. 18 scenarios of
`administrators.feature` pass in Chromium, the other 6 are checked by the unit tests they name. Implementation note:
`implementation-notes/sec-12-setup-code.md`.

### SEC-13 · The web app is served without security headers · P2 · fixed 2026-11-12
**Evidence (measured).** `curl -I /` on a server with `--web`: only `cache-control`, `etag`, `content-type`. No
`Content-Security-Policy`, no `frame-ancestors`/`X-Frame-Options`, no `X-Content-Type-Options`, no `Referrer-Policy`.
Any site can frame a document page or the server settings (click-jacking); nothing limits where a script may come from.
**Fix.** In `SinglePageApp` (and the landing page): `Content-Security-Policy: default-src 'self'; connect-src 'self'
ws: wss:; img-src 'self' data: blob:; style-src 'self' 'unsafe-inline'; frame-ancestors 'none'; base-uri 'none';
object-src 'none'`, plus `X-Content-Type-Options: nosniff` and `Referrer-Policy: no-referrer`. Check Plotly and the
typeset images against it in the browser scripts (Firefox and Chromium) before tightening further.
**Acceptance.** A server test asserts the headers on `/`, an asset and `/admin`; the web e2e scripts pass with them.
**Fixed 2026-11-12** in `claudia_server/security_headers.py`, an ASGI layer inside `HostGuard`: the policy above with
`script-src 'self'` plus the SHA-256 of the start page's two inline scripts (Nuxt's import map and runtime config,
read from the build's `*.html` at start, so no `'unsafe-inline'` for scripts), `connect-src` naming the request's own
host for `ws:`/`wss:`, `worker-src 'self' blob:`, `form-action 'self'`, and `frame-ancestors 'self'
http://127.0.0.1:* http://localhost:*` instead of `'none'`, because the Windows and macOS clients show the web app
in a frame of their local shell page (D251); `X-Frame-Options` is left out, as it cannot name two origins. Plus
`Permissions-Policy: camera=(), microphone=(), geolocation=()`. `/api/swagger` keeps only the framing rule while it
loads from a CDN (SEC-14). Tests: `test_server_security_headers.py`. Checked in Chrome for Testing 153: the seven
browser scripts, the Windows and macOS shell windows (the frame), a Plotly chart and the settings page run with no
CSP report, and an injected inline script is refused; the Linux client's end-to-end test (WebKitGTK 6.0) passes
with it. Not yet checked in Firefox.

### SEC-14 · `/api/swagger` loads from a CDN · P3 · new, open
**Evidence (measured).** FastAPI's default page pulls `swagger-ui-bundle.js` and its CSS from `cdn.jsdelivr.net`, so
opening it tells a third party about the server and runs a script from there, against the privacy promise. It is
linked from the landing page and public on every server.
**Fix.** `docs_url=None` by default (`--api-docs` turns it on), or serve the Swagger assets from the package.

### SEC-15 · Office import reads every part whole and parses some XML with defaults · P2 · fixed 2026-11-17
**Evidence (read).** `claudia_opc_io.read_parts` and the odf readers `zf.read()` every member with no limit on
uncompressed size or member count: a few-MB zip bomb exhausts the server's memory. Most ODF parsing uses
`XMLParser(resolve_entities=False, no_network=True)`, but `odt.py:235` (styles), `xlsx.py` (since 2026-11-13 the
xlsx reader uses a hardened parser, D370; its zip is still read whole) and
`odf_io/package.py:70` use lxml's defaults (lxml 6 resolves internal entities). Import is not on the wire yet (only
export is), which is why this is P2; it becomes P1 the day the import UI (E2.9, E6.9, E9.5, E10.3) sends a file.
**Fix.** One `safe_parts(data, max_members, max_total, max_ratio)` in `claudia-opc-io` that checks `ZipInfo.file_size`
and the ratio before reading, used by every reader; one module-level hardened `XMLParser` used everywhere.
**Acceptance.** A zip of one 2 GB part of zeros (~2 MB on disk) is refused with a sentence before 50 MB of memory are
used; an entity-expansion document is refused or read without expansion, in each of the six readers.
**Fixed 2026-11-17 (stabilisation round).** `claudia_opc_io.check_package` judges the zip directory (member count, part,
total, ratio) before anything is unpacked; `read_parts` and the server's `formats.import_state` call it, so a bomb is
refused for every format. `claudia_opc_io.parse_xml` is the one hardened parser (no entities, no network, no DTD) used
by the docx, odt, xlsx, pptx and odf readers. Tests: `test_limits.py`, `test_xml.py`, `test_server_formats.py`.
The xlsx reader's openpyxl parser was probed: it is already safe, so no extra dependency was added.

### SEC-16 · The LaTeX program setting accepts any executable · P3 · new, open
**Evidence (read).** `PUT /api/admin/settings/typeset` stores any path; `resolve_program` accepts any runnable file.
An administrator is trusted, but with SEC-12 that is anyone, and even without it a stolen admin session becomes
"run this binary on every formula". **Fix.** Accept the setting only after the program answers `--version` with an
XeTeX / pdftocairo banner (in the sandbox), and show what it answered on the settings page.

### SEC-17 · A viewer's connection receives the whole history and chat · P2 · fixed 2026-11-19 (found 2026-11-05)
**Fixed (D1261).** `claudia_server.audience` classifies every pushed event; a viewer is sent content only, her `command`/`branch` events are reduced, her `welcome` has no history parts; `reads=` on every method refuses a viewer the history and the chat (`forbidden`). Tests: `test_server_audience.py`, the golden `tests/method_reads.json`, the updated hub tests. One part is not done: the authorship of the content, SEC-22.

**Evidence (read, `7e619a2`).** The container gives a viewer no key to history and chat blocks (E2.4), but the live
session ignores roles: `HostedDocument._audience` (`hub.py`) filters events by author, recipient and sender only, and
the `log` and `chat_log` methods (`protocol.py`) answer any account. The 2026-11-05 review described this but it never
got a number, so it was never picked up. **Fix.** In `_audience`, history-bearing events and chat go to editors and
owners only; `log`/`chat_log` refuse a viewer with `forbidden`; the web panel shows a viewer "History and chat are
for the document's editors". Decide first whether a viewer may at least see the *document's* public chat (product
call, not a security one). **Acceptance.** Server tests: a viewer's connection receives no `log`/`chat` event and is
refused `log` and `chat_log`; an editor's is unchanged.
**Re-checked 2026-11-20 at `f34365f`.** Merged into `main` with `e2-document-sec` on 2026-11-20. What a viewer still
receives is SEC-22.

## Performance

### PERF-01 · `cells` window cost grows with the whole sheet · P2 · verified open (re-measured)
**Evidence (measured, `54d1245`).** `claudia_server/computes.py` `_cells` line 82 is
`sorted((r, c) for r, c in found.cells if …)`: it scans every cell of the sheet and sorts the matches. Measured on this
machine for one 64×16 window:

| cells in the sheet | window | growth vs 1k |
|---|---|---|
| 1,000 | 0.12 ms | ×1 |
| 10,000 | 0.57 ms | ×5 |
| 100,000 | 3.64 ms | ×30 |
| 500,000 | 21.08 ms | ×172 |

Linear in the size of the sheet, not in the size of the window. The grid asks for such a window on every scroll, and
`Connection.handle` runs synchronously on the event loop, so the whole server pauses for it.
**Fix.** Keep an index per sheet (rows → sorted columns) in `claudia-computes`, maintained by the commands; or cache
chunks per revision.
**Acceptance.** A guard in `scripts/check_debt.py`: window cost at 500k cells ≤ 2 ms and within 2× of the cost at 10k.

**Re-checked 2026-11-12 (`7e619a2`): fixed.** `Sheet.cells_in` keeps a row → sorted-columns index; one 64×16 window
costs 0.11 ms at 10k cells and 0.06 ms at 500k (was 21 ms). Guarded in `test_index_performance.py`.

### PERF-02 · Journal `fsync` on the event loop for every edit · P2 · verified open
**Evidence (read, `54d1245`).** `claudia_container/journal.py` `append` does `flush()` then `os.fsync()`
synchronously (lines 210–211); `filestore.py` `_write` does the same for the plain store. The call path is
`_Live.run` → `connection.handle` (synchronous) → `methods.dispatch` → `document.execute` → store append. So every
keystroke-sized edit fsyncs on the event loop and stalls every document the server holds.
**Fix.** The group commit named in the E2 design (D76 of that document, renumbered D106 here): a writer task off the
loop, several records per fsync, the request acknowledged after its batch is synced. Measure first on a spinning disk
and on a network volume.
**Acceptance.** With a store whose `append` sleeps 50 ms, `ping` latency of other users stays under 20 ms.

### PERF-03 · `users.json` rewritten in full on every user added · P3 · superseded
The sealed container replaced `FileDirectory` for `--dir`; people live in `people.bin` inside the document. Keep the
item only for `--plain-dir`, which is the legacy store.

### PERF-04 · `GET /api/docs` scans the disk on every request · P3 · fixed
The server keeps a listing cache built from the manifests (E2 slice 3).

### PERF-05 · `sheets` recomputes the extent by scanning every cell · P2 · new, verified open
**Evidence (measured, `54d1245`).** `computes.py` `_extent` runs two `max()` passes over `sheet.cells` for every sheet,
and `_sheets` calls it for each. Measured: 0.06 ms at 1k cells, 6.14 ms at 100k, **37.97 ms at 500k** — worse than
PERF-01 and on the same event loop. The client calls `sheets` on open and after structure changes.
**Fix.** Maintain the extent incrementally in `Sheet` as cells are set and cleared (it already tracks a version per
column), or cache it per revision.
**Acceptance.** A guard: `sheets` on a 500k-cell workbook costs ≤ 2 ms.

**Re-checked 2026-11-12: fixed.** `Sheet.extent()` is amortized O(1) (`_rows_live`/`_cols_live`); 0.001 ms at 500k
cells.

### PERF-06 · Packing rewrites the whole zip; threshold packing on the event loop · P3 · verified open
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

### UX-01 · Menus cannot be operated with the keyboard · P2 · verified open
**Evidence (read, `54d1245`).** `web/app/components/MenuBar.vue` still carries `role="menu"` and `role="menuitem"` but
has no `aria-haspopup`, no `aria-expanded`, no `aria-controls`, no arrow-key handling and no focus movement into the
open menu. The only keyboard listener is a global Escape. The ARIA roles promise arrow-key behaviour that does not
exist, which is worse for a screen-reader user than plain buttons would be.
**Fix.** Implement the ARIA menu-button / menubar pattern: `aria-haspopup`, `aria-expanded`, `aria-controls`; focus to
the first item on open; Up/Down/Left/Right/Home/End/typeahead; Escape closes and restores focus; Alt or F10 reaches the
bar.
**Acceptance.** A browser test opens File, moves with arrows, activates an item, and ends with focus back on the grid.

**Re-checked 2026-11-12: fixed (read).** `MenuBar.vue` now has `aria-haspopup`/`aria-expanded` and arrow-key
handling (commit 47519fa). Not yet tried with Orca or NVDA.

### UX-02 · The grid has no accessible structure · P2 · fixed on `bitv`, awaiting commit
**Evidence (read, `54d1245`).** `SheetGrid.vue` has exactly two ARIA attributes: `role="grid"` and
`aria-label="table"` (plus `aria-label="editing cell"` on the editor). No `role="row"`, no `role="gridcell"`, no
`aria-rowcount`/`aria-colcount`, no `aria-rowindex`/`aria-colindex`, no `aria-activedescendant`, no `aria-selected`. A
screen reader cannot say what is in a cell or where it is.
**Why it matters.** D69 names public administration and schools as audiences. In the EU those buyers usually have to
meet WCAG 2.1 AA through EN 301 549 (in Germany BITV 2.0). This is the single biggest gap against that bar, and the
grid is the product.
**Fix.** For the virtualised grid: `aria-rowcount`/`aria-colcount` for the whole sheet, `aria-rowindex`/`aria-colindex`
on rendered rows and cells, `role=row`/`gridcell`/`columnheader`/`rowheader`, `aria-activedescendant` for the active
cell, and a live region for values changed by other people.
**Acceptance.** axe in the browser run passes on the workspace page; an NVDA/Orca script joins the release checklist
(E5.10).

**Re-checked 2026-11-12: still open.** `SheetGrid.vue` has `role="grid"` and still no `row`/`gridcell`,
`aria-rowindex`/`aria-colindex` or `aria-activedescendant`. The grid is the one part of computes a screen-reader user
cannot work with; E5.10 (accessibility baseline) is `todo`.

**Fixed on `bitv` (2026-11-13).** `SheetGrid.vue` now says what it is: `aria-rowcount` 10001 and `aria-colcount` 703 (the
sheet and its header row and column), `aria-multiselectable`, a name that includes the sheet; the column letters are a
`row` of `columnheader`s (row 1); every drawn row is a `row` with `aria-rowindex`, a `rowheader` and its `gridcell`s with
`aria-colindex` and `aria-selected`. Focus stays on the grid and `aria-activedescendant` names the active cell, which is
always drawn, empty or not; its name is "B2, 9600, formula", "B3, error #DIV/0!: …", "B5, empty", with alternatives,
outcomes and the part in a followed computation said in words (`lib/grid-a11y.ts`, tested first). A range, a whole
row or column and a selected object are said once the selection settles, in a polite live region next to the grid
(`Workspace.vue`). The header and row-number layers keep their look by z-order instead of by clipping containers.
**Test:** `web/tests/grid-a11y.test.ts` (words), `web/e2e/grid-a11y.cjs` (structure, the active cell's name through
Home/arrows, the range announcement, and axe-core 4.14 over the whole computes page against WCAG 2.0/2.1/2.2 A and AA:
no violations). Found and fixed on the way, outside the grid: the sheet tab list contained the "new sheet" button
(`aria-required-children`), the Draw button's name did not contain its visible text (2.5.3), and two texts fell below 4.5:1
(the history panel's times on the dark panel, 45% to 62%; the revision label's 80% opacity).
**Not done / not known.** No screen reader (NVDA, JAWS, Orca, VoiceOver) was run, so how they read the row wrappers and
`aria-activedescendant` is unverified, and axe lists items for a person to judge (four contrast checks on overlays, three
names). Whole rows and columns are announced, not marked cell by cell (only the drawn cells carry `aria-selected`). The
other apps are not grids. Another person's or the `ai`'s changes to cells are not announced (the original fix asked for
that): a separate story.

### UX-03 · Dialogs do not manage focus · P2 · verified open
**Evidence (read, `54d1245`).** `Modal.vue` is a plain element with a global `keydown` listener for Escape. No
`<dialog>`, no `showModal()`, no focus trap, no `inert` on the background, no focus restored to the opener. Every
dialog in the app uses it (Share, Prompt, Help, Styles, Recovery key).
**Fix.** Use native `<dialog>` with `showModal()`, which gives the trap, the inert background and Escape for free;
move focus to the first field; restore focus to the opening control on close.
**Acceptance.** After open, `document.activeElement` is inside the dialog; Tab cycles inside it; after close focus is
on the control that opened it.

**Re-checked 2026-11-12: fixed.** `Modal.vue` is a native `<dialog>` opened with `showModal()` (focus trap, inert
background, Escape).

### UX-04 · Text and border colours fail WCAG contrast · P2 · verified open (re-measured)
**Evidence (measured from `web/app/assets/tokens.css` at `54d1245`.)** Ratios computed by the WCAG 2.1 formula, with
`color-mix(… transparent)` treated as alpha compositing over the stated background:

| Pair | Ratio | Needs | |
|---|---|---|---|
| `--muted` (ink 58%) on `--surface` white | 4.18:1 | 4.5 | fail |
| `--muted` on `--paper` | 4.05:1 | 4.5 | fail |
| `--muted` on `--mist` | 3.85:1 | 4.5 | fail |
| `--rose` as error text on white | 4.17:1 | 4.5 | fail |
| `--teal` as text on white | 3.90:1 | 4.5 | fail |
| `--apricot` as text on white | 2.11:1 | 4.5 | fail |
| `--line` (ink 14%) as a field border on white | 1.33:1 | 3.0 | fail |
| `--line` on paper | 1.32:1 | 3.0 | fail |
| `--ink` body text on paper | 15.14:1 | 4.5 | pass |
| white on `--iris` | 6.46:1 | 4.5 | pass |
| `--iris` text on paper | 5.84:1 | 4.5 | pass |

**Fix, with the numbers.** `--muted` at **65% ink** clears both grounds (5.24:1 on white, 4.74:1 on mist); 70% gives
more room. The error rose and the teal text variant need darker values. `--line` **cannot be fixed by raising the ink
percentage alone** for its use on form fields: 40% ink still only reaches 2.48:1, and 3:1 needs about **50% ink**,
which is far too heavy for the decorative dividers that also use the token. Split it: keep `--line` for dividers and
add a `--line-field` at about 50% ink for input and control boundaries. The dark history panel was not measured here.
**Acceptance.** A token test (a script in `scripts/`) computes every pair and fails below the thresholds, so the
palette cannot regress silently.

**Re-measured 2026-11-12 (`tokens.css`): mostly fixed.** `--muted` 5.26:1 on white, 5.03:1 on paper, 6.31:1 dark;
`--line-field` ≥ 3:1 in both themes. Residue: creates' `--app-dark` `#b9651c` is 4.25:1 on white, used as normal-size
text (`FooterBar.vue` `.tabs button.on`, `StyleSpec.vue`, `SlideWorkspace.vue`): needs ≥ 4.5:1 (e.g. `#a75a17`). And
`--iris` as text on the dark surface is 2.44:1 — nothing uses it that way today, but nothing stops it. **Acceptance.**
A vitest that reads `tokens.css` and checks every text token against both surfaces, so the next colour cannot regress.

**Fixed on `bitv` (2026-11-13), awaiting commit.** `web/tests/tokens.test.ts` is that vitest (arithmetic in
`web/tests/contrast.ts`). It showed the residue was wider than measured: `--app-dark` is also text on the app's own soft
tint, where computes' teal measured 4.36:1 as well, and the suggested `#a75a17` for creates would have reached only
4.49:1 there. Now teal `#0d7768` (4.73:1 on its soft tint, 4.92:1 on paper) and apricot `#9c5314` (5.05:1, 5.19:1);
composes' `#b8386a` already passed. `--iris` as text on the dark surface stays unfixed and unguarded: nothing uses it.

### UX-05 · No dark mode · P3 · verified open
**Evidence (measured).** `web/app/assets/tokens.css` contains **zero** `prefers-color-scheme` rules, and `--surface` is
a hard-coded `#ffffff`. E0.3 lists a dark/light switch as an acceptance criterion and GNOME apps follow the system
setting. (The server's own fallback landing page in `app.py` does implement dark mode, which makes the gap visible.)
**Fix.** Define dark values for every token, follow the system setting, and let the shell contract pass the OS value.

**Re-checked 2026-11-12: fixed.** `theme.ts` follows `prefers-color-scheme` with a person's override;
`:root[data-theme='dark']` in `tokens.css`.

### UX-06 · Web menu differs from decisions D4/D5 · needs decision
D4 says four header-bar menu buttons: File, Edit, Tools, Help. The web app has six menus (File, Edit, Format, View,
Tools, Help) in a separate menu-bar row, and the File items read *New sheet…, Save, Save with a name…, Share…, Close
document* rather than *Open, Save, Save As, Exit*. See also UX-09, which is the consequence.
**Decision needed.** Either record the six-menu structure as the decision and update D4/E5.1, or fold the menus back
into the four and align the labels.

### UX-07 · Website blocks pinch-zoom · P2 · open
`user-scalable=no` in the viewport meta of the home page (WCAG 1.4.4 / 1.4.10). Not re-checked in this round; the
website was out of scope.

### UX-08 · Open and Create sit side by side · P3 · open
A mistyped document name on *Open* gives "the name or password is not right (or there is no such document)", and one
click on *Create document* then makes the person owner of a new empty document.
**Fix.** While the server lists documents, say when the typed name is not in the list; mark the default button by
context; make placeholders visibly lighter than entered text.

### UX-09 · Six web menus against four in D4; the Linux shell maps between them · P2 · new
**Evidence (read, `54d1245`).** The Linux shell carries a mapping table (`manifest.py` plus `data/webroutes.json`) and
a page adapter (`data/shim.js`) that *clicks the web app's own menus as a person would* to carry out a native menu
action, polling every 750 ms to read which items are enabled or ticked. This was a deliberate stop-gap (the owner asked
that the web app not be changed), and a drift-guard test fails when a web label a route uses is renamed.
**Why it matters.** It is a DOM click-path between two menu structures that D4 and E5.1 say should be one manifest. It
is fragile by construction, it costs a poll every 750 ms, and it has to be rewritten for every shell. The cost grows
with each app and each new menu item.
**Fix.** E5.1 as written: one menu and action manifest that generates the GMenu XML, the Neutralino menu and the web
menu, and the web app implementing the shell contract directly. Then `shim.js` and `webroutes.json` are deleted.
Settling UX-06 is a precondition.

### UX-11 · The admin sign-in screen had no way back except the browser's Back button · P2 · fixed
**Evidence (read, `441d6cb`).** Reported by the owner: opening the connectivity indicator's "Manage this server…"
on a server that already has an administrator lands on `AdminLogin.vue`. `AdminShell.vue` (shown once signed in)
has a `×` "Close" button (`location.href = '/'`); `FirstAdminSetup.vue` has "Skip for now" / "Keep this server
local for now" (`keepLocal()`, same target). `AdminLogin.vue` had neither — nothing in its template emits a way
out, so the browser's own Back button was the only escape. Investigated while trying to reproduce a related report
that a freshly created document seemed to go missing after exactly this click-through-and-Back path; the document
itself turned out fine (D5's "Open creates on the server, Save checkpoints" already means there is no unsaved-draft
window to lose), but this dead end is real and independent of that.
**Fix.** Gave `AdminLogin.vue` the same `close` emit and `×` button `AdminShell.vue` already uses (same markup,
same `.close` styles), and wired it in `AdminApp.vue` to the existing `close()` → `location.href = '/'`.
**Acceptance.** Verified with a real browser against a built app: an administrator account is already configured,
`/admin/` renders the sign-in form with the `×` visible, clicking it returns to `/` (the Open dialog) without
touching browser history.

### UX-12 · Open dialog goes blank if the server has an access secret · P2 · fixed
**Evidence (measured, `441d6cb`).** The backend correctly gates `GET /api/docs` behind the access secret
(`Gateway.accepts_secret`, `app.py`): with one set, the endpoint answers `401 {"detail": "this server needs its
access secret"}`. `OpenDialog.vue`'s `loadServer()` only special-cased a `404` from that fetch; every other status,
401 included, fell into the same branch as success and ran `documents.value = said.documents` — `undefined` for an
error body with no `documents` key. The template's `v-else-if="!documents.length"` then threw
`TypeError: Cannot read properties of undefined (reading 'length')` on render. Confirmed with Playwright against a
real server with an access secret set: page body text came back empty and the console showed exactly that
`TypeError`. This blanks the *entire* Open dialog, not just one document, and needs no editing at all to trigger —
just loading `/` on a secret-protected server. Backlog's E3.9/E3.1 status notes already flagged "the access-secret
prompt" (a way to *supply* a secret from this dialog) as not built; this was the unhandled-exception shape of that
same gap, not a separate missing feature.
**Fix.** Pulled the whole "ask a server for its document list" step into a pure, testable function,
`fetchDocsListing()` in `web/app/lib/open.ts` (mirroring `appOfServer()`'s own extraction for UX-10, and
`admin-api.ts`'s `call()` for how it turns a `detail` field into a message): any non-OK status becomes a
`{ error }` result using the server's own `detail` message when there is one, a 404 keeps its existing wording, and
a 200 whose body has no `documents` array is treated as an error rather than assigned anyway. `OpenDialog.vue` now
calls it and sets `listError` on the error branch, exactly as it already does for the old 404 case — no new UI,
just no longer trusting an unexpected shape. The `Listed` interface moved from the component into `open.ts`
alongside it, since it's now shared.
**Acceptance.** `web/tests/open.test.ts`, `describe('fetchDocsListing', …)`: a normal 200, a 404 (unchanged
wording), a 401 with a `detail` (surfaces it verbatim instead of crashing — this is the regression test), a 500
with no usable `detail` (generic message), a 200 with no `documents` array, and a network failure — seven cases,
all passing. Re-verified live: with an access secret set, `/` now renders the Open dialog's full chrome (servers
sidebar, headline, create-document form) with "this server needs its access secret" where the list would be,
instead of a blank page; zero JS `pageerror`s.

### UX-13 · `help_search` leaks one app's topics into another's; composes has none of its own · P2 · fixed
**Evidence (read + measured, `41f8f39`).** Reported by the owner, four composes inconsistencies in one batch; this
is the help-system one. `core_methods.help_search` (`protocol.py`) called `default_library().search(query)` with
no app at all, so the per-app `apps` front matter every topic file already carries (`help.py`'s `Topic.apps`,
documented since E13.1) was simply never read back out. Confirmed by running a composes document's `help_search`
against the real server code: it returned `computes.writing-a-formula`, `computes.looking-up-a-value` and
`computes.summing-with-a-condition` — three spreadsheet topics, verbatim, inside a word-processor's own Help tab.
The reverse leak (composes' own topics into computes) could not also be demonstrated at this commit because
composes had zero topics of its own — an empty `help/` folder was the second half of the same report: scoping was
missing *and* there was nothing yet to scope.
**Fix.** `HelpLibrary.search(query, *, app=None)` gained the optional keyword: when given, it keeps a topic only
if `app` is in that topic's own `apps`, or `apps` is empty (a topic naming no app is for every app — this is how
`typeset.configure-latex` keeps showing up from every app that can embed LaTeX). `_help_search` now passes
`ctx.document.model.app` along; `_help_topic` is deliberately left unscoped, since an id already names one exact
topic the same way a direct link works from anywhere. This is a Minor, additive change to `claudia_server`'s
public API (`docs/versioning.md`): version 0.18.0 → 0.19.0, changelog entry, snapshot regenerated
(`tests/api/claudia_server.json`). Gave composes its first two topics (`composes.editing-a-style`,
`composes.asking-ai-to-review`) so its Help tab is not merely correctly empty.
**Acceptance.** `packages/claudia-server/tests/test_server_protocol.py`, the `help (E13.1, E13.3)` block: a
computes document's `help_search` never returns composes' own topics and the reverse; a topic naming several apps
(`typeset.configure-latex`) still shows from each of them; `query=""` on a scoped `help_search` gives every topic
for that app, not every topic in the library; composes' own new topics are found by a `style` search;
`help_topic`'s existing behaviour (full text by id, unknown-id error, every role including `ai` can read) is
unchanged, and a new test confirms it is *not* re-scoped — fetching a computes topic's id from a composes document
still works. 10 tests, all passing; the one that depends on composes' own content (`test_help_search_finds_composes
_own_new_topics`) was red before the two topic files existed, green after.

### UX-14 · "Edit this style…" gallery applies and closes on click instead of showing the style to inspect · P2 · fixed
**Evidence (read + measured, `41f8f39`).** Second of the owner's four composes reports. `StyleMenu.vue`'s gallery
click handler called `choose(id)`, which ran `host.apply(id)` — writing the clicked style onto the caret's current
paragraph — and then `emit('close')`. There was no way to look at a style's CSS or controls without first applying
it to whatever the cursor happened to be sitting in, and the menu vanished the instant you clicked, before the
look below it could even be seen. Confirmed by reading `StyleMenu.vue`/`StyleSpec.vue`/`style-host.ts` together:
`StyleSpec.vue` always read `props.host.current`, which is exactly the document's own current style — there was
no separate notion of "the style I am looking at" distinct from "the style under the caret" anywhere in the three
files. `StylesDialog.vue` ("All styles…") and `StyleBar.vue` (the toolbar's quick-apply list) were checked and
confirmed unaffected — neither goes through this gallery-click path.
**Fix.** `StyleEditor` (`web/app/lib/style-host.ts`) gained `pick(id)`, `isPicked` and `canDeviate`: picking a
style only changes what `editor.current`/`editor.look` show, never the document, and the caret's own paragraph is
left untouched. The gallery's click handler now calls `editor.pick(s.id)` directly — no `apply`, no `close`.
Picking a style other than the caret's own forces scope to "every use" and disables "this paragraph only" (there
is no selection to split off from a style that is merely being browsed); this is also how a change made while
picking a style is written — to that style, for everyone, never as a deviation of whatever the cursor is really
in. `StyleMenu.vue` now constructs the one `StyleEditor` and passes it down to `StyleSpec.vue` as a prop (moved
from being constructed locally in `StyleSpec.vue`), so picking in the gallery and the controls below it share the
same state; a small "here" badge marks which gallery row is the caret's real style whenever that differs from
what is being inspected. **Decision taken:** "this paragraph only" is disabled, not merely defaulted away, while
picking another style — the owner's choice between the two when asked.
**Acceptance.** `web/tests/style-editor.test.ts`, `describe('picking a style to inspect, without applying it
(UX-14)', …)`: picking sends nothing to the document and leaves the caret's own style alone; picking forces
"every use" and disables deviation; an edit made while picking changes the picked style, never a deviation of the
caret's own; picking the caret's own style back behaves exactly as not picking at all — 6 new tests, all red
before `pick()` existed, green after; full suite 473/473, `vue-tsc --noEmit` clean. `web/e2e/styling.cjs` gained a
matching browser scenario (pick Heading 1, confirm the paragraph is untouched and the "here" badge appears, edit
while picked changes Heading 1 globally, undo and pick back restores the ordinary controls) — written against the
real component source and existing selectors, but **not executed** in this sandbox: Playwright's browser-binary
download host is outside the sandbox's network allowlist (confirmed via the proxy's own status endpoint). Running
it for real, or in CI where Chromium is already installed, is the one piece of this fix not yet machine-verified.

### Note on PERF-04
While reproducing the above, `bugtracker.md`'s own index still lists `PERF-04` as "fixed (listing cache)", but
`SealedDocuments.documents()` — the provider the real server uses today — globs and re-reads every container
file's manifest on every call (`sealed.py`, `documents()`). No cache currently exists in that path. Not a
correctness bug (the listing is always fresh, which is why neither UX-11 nor UX-12 traces back to a stale cache),
but whatever closed PERF-04 belonged to an earlier, now-replaced store, and the index entry is stale.

---

### UX-16 · A submenu opened by hovering closes again when its item is clicked · P2 · fixed
**Evidence (2026-11-10, `301ded6`).** `e2e/demo.cjs` could not reach File ▸ Manage ▸ Share…. In `MenuBar.vue`,
hovering a flyout parent opens it (`enterItem` sets `activeSub`), and clicking the same parent *toggled* `activeSub`
— so a mouse, which always hovers before it clicks, closed the flyout it had just opened.
**Fix.** A click on a flyout parent only opens it. The keyboard path is unchanged.

### UX-17 · A regional browser locale asks for a catalog that does not exist · P2 · fixed
**Evidence.** Every page in a browser set to `en-US` logged `404 /i18n/en-US.json` (found as console errors by the
e2e scripts). In `de-DE` the same lookup missed `de.json`, so the app stayed English, and Config ▸ App Language
ticked neither entry, because it compared `en`/`de` with the full tag.
**Fix.** `appLanguage(tag)` in `web/app/lib/i18n.ts` maps a tag to an App Language (exact, then by language, then
English); the catalog and the menu use it. Tests in `web/tests/i18n.test.ts` (the no-fetch ones now count calls: a
throwing stub could not tell, because `loadCatalog` swallows errors).

### UX-18 · The formula hint covers the column letters while a formula is typed · P2 · fixed
**Evidence.** `e2e/pointing.cjs` failed now and then on "a whole column from its header": the click landed on
`.formulaHelp`, which appears under the formula bar exactly over the column letters while `=SUM(` is being typed.
**Fix.** The hint takes no pointer events; it only reads.

### UX-19 · Picking the caret's own style back pins it · P2 · fixed
**Evidence.** `e2e/styling.cjs`: after looking at Heading 1 and picking Body text back (UX-14's gallery), making the
paragraph bold "this paragraph only" created the new style, but the menu stayed on Body text — no invitation to name
the new style, and the next change went to Body text for everyone.
**Fix.** `StyleEditor.pick` treats the caret's own style as "follow the caret again". Test in
`web/tests/style-editor.test.ts`.

### UX-20 · The AI in computes does nothing and points at a switch no client has · P1 · fixed 2026-11-12
**Evidence (measured, `7e619a2`).** `web/e2e/demo.cjs` failed at "ai done": `@ai build an example budget` was
answered "You asked me in suggest mode … Switch to act mode". No client sends `ai_mode` yet, and `ai_mode.parse_mode`
read a missing mode as *suggest*, although `chat`'s own description and the E7.7 build note say "a client that sends
none gets act"; computes cannot propose yet (E7.8), so the AI wrote nothing, ever. **Fix (agreed 2026-11-12).**
`UNSAID_MODE = ACT` for a request without a mode; `DEFAULT_MODE` stays *suggest* for a client with the switch (D262).
Tests in `test_server_ai_account.py`; `demo.cjs` passes again.

### UX-21 · The chat promises an AI where none answers · P2 · new, open
**Evidence (measured, screenshots of `slides.cjs`).** creates' chat says "Write to everybody, or @ai to ask the
assistant. Say @ai help to see what it can do", but creates has no AI user (no `ai` avatar; E7.9 is `todo`). Until
UX-20 the computes refusal also named "act mode", a switch that exists in no client. **Fix.** The hint comes from what
the server says it has (`hello`/`people` already list `ai`): no `ai` participant, no `@ai` in the hint. Any message
that names a control must name one the person can see. **Acceptance.** A web unit test of the chat hint with and
without an `ai` participant.

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

### UX-10 · An empty server greets everybody as computes, whichever app it serves · P2 · fixed
**Evidence (measured, `22d5fe4`).** `./start.sh all` runs three servers — computes 8765, composes 8766, creates 8767.
All three landing pages showed the computes headline, "Think with your data. Open a table, or start a new one", and
the top bar said only "claudia". Opening a document on each port gave the right app every time, so the servers and
the launcher were never wrong; only the greeting was. The effect was worst on a fresh machine, where every folder is
empty and all a person sees is three identical pages claiming to be the table app.
**Cause.** `OpenDialog.vue` worked the app out as `documents.value[0]?.app ?? 'claudia'` — from the *first listed
document*. With no documents there was nothing to read, and the copy fell through to the computes wording, which is
the fallback branch. `/api/docs` has answered `{"app": ..., "documents": [...]}` all along; the page took the
documents and dropped the app.
**Fix.** `appOfServer()` in `web/app/lib/open.ts`: believe the server, fall back to a listed document for an older
server that does not say, then to claudia in general. Extracted into `lib` rather than left in the component so it
could be tested — the web tests cover `lib`, and there is no component harness. Four tests in `web/tests/open.test.ts`.
Re-measured on all three ports with empty document folders: computes says "Think with your data", composes "Write
together", creates "Say it on a slide", and each top bar names its own app.
**Acceptance.** `tests/e2e/test_greeting.py` — the first test in the project that drives a real browser. It runs
`./start.sh all`, opens each of the three ports in Chromium and reads `data-app` and the headline off the page.
Confirmed to fail on `22d5fe4` for the right reason before the fix (all three said `app: claudia` and "Think with
your data"), and to pass after it. `scripts/check_debt.py` runs it as the `e2e greeting` step and skips it, saying
which is missing, where the web app is not built or there is no Chromium; CI has an `e2e` job that installs both.
**Why nothing caught it.** Every layer below the rendered page was correct — the launcher, the three servers,
`/api/docs` — and the web tests cover `web/app/lib`, not the page. The bug lived in the one place nothing looked.
**Not the cause, though it looks like one.** computes and creates show "No styles yet" under *Format*: those menus
are deliberately inert (D125) and the style UI for both is still to come.

### UX-15 · The PowerPoint exporter is dead, and loses every colour once it is not · P1 · fixed
**Evidence (measured, `441d6cb`).** `import claudia_creates_io.pptx` raised `ImportError: cannot import name
'Style' from 'claudia_creates'` — so every .pptx export and import failed on the first call, and nine of the
package's own tests failed. `ruff` had three errors at this commit for the same reason, and the catalogue's
`pptx-*` and `docx-*` entries were failing too.
**Cause.** Two branches met. The shared object layer (D177) removed creates' own `Style` dataclass, turned
`SlideObject` into a PEP 695 type alias — which cannot be called — and made an object's words a frozen
`Paragraph` whose runs must cover its text exactly (D181). The additive-io branch was written against the flat
object it replaced: it imported `Style`, called `SlideObject(...)`, read `.kind/.x/.text/.style` off a
`VisualObject`, indexed `BUILTIN_STYLES` as if it were a dict, and its tests and the catalogue's `spec.py` files
did the same. Nothing caught it because neither branch's own gate ran against the other's code.
**And a quieter one behind it.** Once it imported, `slides_to_pptx` read `computed` CSS and looked for a
`#rrggbb`. Since D201 every built-in style names a role: `fill: @accent/14` holds no hex, `_rgb` found none, and
the fill and the border were dropped silently. A deck exported from a brand-new presentation came out colourless.
**Fix.** The import half was fixed on `main` independently (the `xlsx-docx-pptx-additive-io` merge, #23): the
importer builds a body and an anchor, `apply_edits_to_pptx` reads `.body`/`.anchor`, and the catalogue's
`spec.py` files were rewritten the same way. When `shapes-n-images` was rebased onto `main` (2026-11-10) `main`'s
version of all of that was kept and this branch's duplicate (`_object`, `claudia_test_documents.edits`) dropped.
What this branch adds on top is the colour half: both `slides_to_pptx` and `apply_edits_to_pptx` resolve against
the document's own style book and palette (`_look`) instead of reading `computed`; `_rgb` reads `rgb()` and
`rgba()` as well as hex, and flattens a translucent colour over the palette's `page`, because a solid pptx fill
has nowhere to keep an opacity and dropping the 14% would export a pale wash as full-strength iris (D211).
**Two regression tests** pin the part no test covered: that a shape's colours reach the file at all, and that
changing a role changes what the file holds.
**Why nothing caught it.** The two branches were each green on their own. A merge that is clean to git can still
be broken in Python — a removed name, an alias that stopped being callable, a dataclass that became frozen — and
nothing runs the other side's tests until both are on one branch.

### PROC-01 · No CI workflow in the repository · P1 · fixed
`.github/workflows/ci.yml` exists at `54d1245`: a Python matrix over ubuntu, windows and macos running
`scripts/check_debt.py`, a web job (`npm ci`, `nuxt prepare`, `vitest`, `vue-tsc`), a Monday schedule and
`workflow_dispatch`. Whether it has ever run green on Windows and macOS is still unknown from the tree alone.

### PROC-02 · The quality gate prints "everything is clean" when half of it was skipped · P2 · fixed
**Evidence (measured, `54d1245`).** Run in a fresh clone without `npm install`:

```
-- ruff: ok      -- mypy: ok       -- vulture: ok    -- tests: ok      -- docs: ok
-- perf claudia-core: ok           -- perf claudia-computes: ok
-- web tests: skipped (run `npm install` in web/ first)
-- web types: skipped (run `npm install` in web/ first)
-- mypy linux client: ok           -- linux client tests: ok

Technical debt check: everything is clean.      [exit 0]
```

**Why it matters more than it looks.** `scripts/check_debt.py` has no `--ci` flag, and `.github/workflows/ci.yml` calls
it with no arguments. The Python job never runs `npm install`, so **in CI the web checks are skipped on all three
operating systems and the gate still reports clean and exits 0.** The separate `web` job does run vitest and `vue-tsc`
on ubuntu, so the checks are not lost — but the gate's own verdict is untrue, and the Linux-client tests skip the same
way wherever `/usr/bin/python3` lacks pytest and jsonschema.
**Fixed.** `check_debt.py`'s `verdict()` never reports "clean" over a skip — the summary is "clean except skipped: …"
whenever anything skipped, named, whether or not `--ci` allow-lists it. `--ci` turns any *unlisted* skip into a
failure. `ci.yml`'s Python job now runs `check_debt.py --ci --allow-skip "web tests" --allow-skip "web types"
--allow-skip "linux client tests"` — exactly the three checks the separate `web` and `linux-client` jobs cover for
real on their own runners; any other skip still fails the build. (D133)
**Acceptance — met.** `tests/test_check_debt.py::test_ci_catches_the_real_bug_with_no_node_modules` feeds this
checkout's own real skip (no `web/node_modules`) through `verdict(..., ci=True, allow_skip=set())` and asserts it
fails — the bug's own reproduction, now a standing regression test.

### PROC-03 · Work described as delivered is not in the repository · P2 · fixed
**Evidence (measured, `54d1245`).** `e4-e6-formulas-notes.md` describes point-and-click cell references for E6.3 as
built on 2026-11-03: `web/app/lib/pointing.ts`, `web/tests/pointing.test.ts` with 22 cases, `REFERENCE_COLORS`,
`slotAt`, and a nine-case browser scenario `npm run e2e:pointing`. None of it exists:

```
ls web/app/lib/pointing.ts          -> No such file
git log --all -- web/app/lib/pointing.ts -> no commits, on any branch
grep -rl "REFERENCE_COLORS\|slotAt" web/ -> nothing
grep "e2e:pointing" web/package.json -> nothing
```

**Why it matters.** The delivery model is "Claude produces a patch, the owner creates the branch and commits". A patch
can be lost in that gap without anybody noticing, and the notes then record a feature as done that nobody can use. It
also makes the notes an unreliable basis for deciding what to build next — which is exactly what they are for. This
one was caught only because the status of every backlog item was re-derived from the code in this round.
**Fixed.** The owner rebuilt and committed the E6.3 pointing work directly (confirmed in the tree at `13d1c80`:
`web/app/lib/pointing.ts`, 22 cases in `web/tests/pointing.test.ts`, the nine-case `web/e2e/pointing.cjs`), so this
round's patch covers only the second half: the rule that a note may only say "built" with the commit that carries it
(status lives in `backlog.md`, derived from the code), and the cheap guard —
`tests/test_notes_claim_built_files.py` greps every "built" paragraph under `claudiaoffice-log/` for a root-relative
path and fails if that path is not in the tree. `e4-e6-formulas-notes.md` and `backlog.md`'s E6.3 card are corrected
to match what is now actually in the tree.
**Acceptance — met.** The claim is true in the tree (`13d1c80`) and the note and `backlog.md` match it; the new guard
would have caught the original false claim (proved by temporarily reintroducing it and watching the test fail).

### CODE-01 · No coverage, no web lint; Playwright not declared · P2 · fixed (2026-11-10)
**Evidence (read, `54d1245`).** No `pytest-cov` or coverage settings in `pyproject.toml`; no eslint, prettier or Biome
in `web/package.json`; the `e2e` scripts run `node e2e/*.cjs`, which needs Playwright, and Playwright is not in
`devDependencies`.
**Why it matters.** `CONTRIBUTING.md` promises TDD. Without a coverage number and a trend there is nothing to check
that promise against — and the test suite is large enough (≈1,321 Python tests, 195 web tests) that the question is
now about where the gaps are, not whether tests exist.
**Fix.** `pytest-cov` with a floor per package, starting at the measured value and ratcheting up; a linter for `web/`;
declare Playwright.
**Done 2026-11-10.** Playwright was declared in the QA round. The gate's `tests` step now runs with `--cov` (it costs
nothing measurable on Python 3.14) and a new `coverage` step holds each of the fifteen packages to a floor in
`pyproject.toml` (`scripts/check_coverage.py`, `--ratchet` to raise them), from 83% (composes) to 100% (opc-io). The
floors are held on Linux with TeX, where every test runs; the check skips elsewhere and CI allows that skip only off
Linux. `web/` has ESLint (`@nuxt/eslint-config`, no stylistic rules; 172 findings fixed or turned off with a reason)
and `npm run coverage`, which holds `app/lib` to thresholds of 88% statements, 90% branches, 80% functions. Both run
in the gate and in CI's `web` job. Notes: `implementation-notes/implementation-notes-coverage-and-lint.md`.

### CODE-02 · 26 build files tracked in `web/dist` · P3 · fixed (2026-11-10)
**Evidence (measured).** `git ls-files web/dist` returns 26 files. `.gitignore` names `web/.nuxt` and `web/.output` but
not `web/dist`, and `docs/web.md` builds to `web/.output/public`, so `web/dist` is stale output.
**Fix.** `git rm -r --cached web/dist` and add it to `.gitignore`.

### CODE-03 · README is out of date · P3 · open
Not re-checked in this round.

### CODE-04 · Untyped functions escape the type check · P3 · verified open
**Evidence (read).** `pyproject.toml` sets `check_untyped_defs = true` but not `disallow_untyped_defs`, so a function
with no annotations is not checked against its signature — for example `SinglePageApp.get_response(self, path, scope)`
and `Gateway._hello` in `app.py`.
**Fix.** Turn on `disallow_untyped_defs` for `claudia_core` first (nearly typed already), then package by package with
per-module overrides.

### CODE-05 · Dead branch in `Gateway.admit`; stale docstring in `state.py` · P3 · fixed (2026-11-10)
**Evidence (read, `54d1245`).** `app.py` lines 232–235 still hold the branch commented "(cannot happen; keeps verify's
checks)".
**Fix.** Remove the branch with its test, or replace the comment with an assertion that states the invariant.
**Update 2026-11-10.** The branch is not dead: the user directory is kept apart from the documents, so a creation that
died between adding the owner and writing the document leaves an account behind; `test_server_gateway_threads.py`
reaches it with a directory that knows the user. An assertion broke that test. The comment now says what the branch
is for. The `state.py` half is still open.
**Update 2026-11-10, later.** `state.py` said the folder held the server's "encryption key and its TLS certificate".
There is no server-wide encryption key — document keys live in memory only (`sealed.py`) — and the folder also holds
the admin settings and the list of administrators (`admin/`). The docstring now lists what is there and why it is
kept apart from the documents; `--state-dir`'s help said "its certificate" only and was corrected the same way.

### CODE-06 · `--max-connections` is per document, not per server · P3 · open
Rename to `--max-connections-per-document`, document it, and keep the server-wide caps from SEC-02 separate.

### CODE-07 · `uv.lock.rej` committed at the repository root · P3 · fixed
**Evidence (measured).** `uv.lock.rej` is tracked at the root: rejected hunks from a failed `git apply` of a lock-file
update. It shows two things that did not land: `claudia-creates` as a dependency of `claudia-server`, and a
`cryptography` floor moving between `>=43` and `>=44`.
**Why it matters.** CI runs `uv sync --locked`, so a lock file that disagrees with the package metadata fails the build
for everyone. The `cryptography` floor is not cosmetic: Argon2id first appears in `cryptography` 44, and the container
depends on it, so a `>=43` floor allows an install that cannot open a document.
**Fixed.** `uv.lock.rej` deleted (and its deletion staged); `claudia-server`'s `pyproject.toml` floor corrected to
`cryptography>=44`; `uv.lock` regenerated with `uv lock` — its `claudia-server` block now correctly lists
`claudia-creates` as a dependency.
**Acceptance — met.** `uv sync --locked` succeeds from a fresh clone; `git ls-files '*.rej' '*.orig'` is empty; the new
`tests/test_repo_hygiene.py::test_no_rej_or_orig_files_are_tracked` fails the gate if a `.rej` or `.orig` file is ever
tracked again.

### CODE-08 · `ruff format --check` fails; the gate does not run it · P3 · fixed
**Evidence (measured, `54d1245`).** `uv run ruff format --check .` reports **1 file would be reformatted**
(`docs/conf.py`). `scripts/check_debt.py` runs `ruff check` but never `ruff format --check`, so the repository has no
enforced format and the drift is invisible.
**Fixed.** `docs/conf.py` reformatted; `ruff format --check .` added to `check_debt.py` as its own named check
("ruff format"), distinct from "ruff" (D133). `pyproject.toml` also excludes `claudiaoffice-log` from ruff's scope —
an illustrative code fence in a notes file was tripping the formatter with no source to fix.
**Acceptance — met.** `tests/test_check_debt.py::test_ruff_format_is_its_own_check` asserts the gate runs it as a
named check; `uv run ruff format --check .` now passes clean.

### CODE-09 · e2e scripts exist without `package.json` entries · P3 · fixed (2026-11-10)
**Evidence (measured).** `web/e2e/` holds `composes.cjs`, `demo.cjs`, `recovery.cjs`, `resilience.cjs`, `slides.cjs`
and `styling.cjs`. `web/package.json` has scripts for only four of them: `e2e`, `e2e:composes`, `e2e:slides`,
`e2e:resilience`. `styling.cjs` and `recovery.cjs` — the scenarios for the two newest features — can only be run by
typing the path.
**Fix.** Add `e2e:styling` and `e2e:recovery`, or one `e2e:all`; and a test that every file in `e2e/` has a script.

### CODE-10 · `main` at `558f429` has a real `SyntaxError` in 10 files: a buggy `ruff format` landed invalid syntax · P1 · fixed
**Evidence (measured, a fresh clone of `main` at `558f429` — "QA finding fixed: quality signals work", the commit
that landed D133/CODE-08).** Ten files parse with `python3 -c "import ast; ast.parse(open(f).read())"` to a real
`SyntaxError: multiple exception types must be parenthesized`, not a lint opinion:
`docker/healthcheck.py`, `packages/claudia-client/src/claudia_client/trust.py`,
`packages/claudia-computes/src/claudia_computes/formula/forms/reference.py`,
`packages/claudia-computes/src/claudia_computes/formula/operators.py`,
`packages/claudia-computes/src/claudia_computes/functions/base.py`,
`packages/claudia-computes/tests/test_computes.py`, `packages/claudia-core/tests/helpers.py`,
`packages/claudia-creates/tests/test_slides.py`, `packages/claudia-typeset/src/claudia_typeset/cache.py`,
`scripts/api_surface.py`. Every one is the same shape:
```
-        except (OSError, ValueError):
+        except OSError, ValueError:
```
`except A, B:` is Python 2 syntax; Python 3 refuses to parse it at all. `pyproject.toml` pins `ruff>=0.6` with no
upper bound, and `uv.lock` resolves **ruff 0.17.3** (2026-10-27); fed the valid, already-parenthesized form, this
`ruff` version's formatter reformats it into the invalid form above — confirmed directly with
`uv run ruff format --diff` on each file in isolation. This is almost certainly how it got into `main`: CODE-08's own
fix ran `ruff format .` to reformat `docs/conf.py`, and a real (non `--check`) run touches the whole tree, so the
same bug struck these 10 unrelated files and the broken result was committed alongside the intended fix. CODE-08's
"`ruff format --check .` now passes clean" was true only against whichever `ruff` resolved at that moment —
`ruff>=0.6` let a later, regressed release drift underneath it before anyone ran the check again.
**Why it matters.** This is not a style nit: a fresh checkout of `main`, exactly as the owner asked this round's work
to start from, fails to import `claudia_client.trust`, three `claudia_computes` modules, and the rest, in whatever
runs them first. It was caught only because this round's own gate run (`check_debt.py`, with CODE-08's check now
actually exercised) flagged `ruff format` as failing and the diff looked backwards from a real fix.
**Fixed.** The parens are restored in all 10 files; each now parses and matches its pre-breakage, correct form.
Bisected every published release: 0.6–0.14.x format this correctly, every 0.15.0–0.17.4 (the latest) strips the
parens — no upstream fix exists yet. `pyproject.toml` now pins `ruff>=0.6,<0.15`; `uv lock` resolved **0.14.14**,
which also wanted two small, unrelated, pre-existing reformats (a docstring's trailing space before `"""`, a blank
line after a `def`) — applied with `uv run ruff format`, since those two are genuinely correct under the pinned
version and not the bug.
**Acceptance — met.** The 10 files parse (`ast.parse`) and keep `except (A, B):`; `uv run python
scripts/check_debt.py --ci --allow-skip "web tests" --allow-skip "web types"` — CI's own invocation — exits 0, with
`ruff format: ok`.

### CODE-11 · Windows client: stale generated menu, and a test that depends on the folder name · P3 · fixed
**Evidence.** `generate_menu.py composes --check` failed (the manifest gained App Language and more since the file was
generated), and `defaultRepo` was tested with `endsWith('claudia')`, which fails in a clone called anything else.
**Fix.** Menus regenerated for all three apps (`--all`, as `npm run generate-menu` does); the test checks what is in
the folder instead of its name.

### CODE-12 · `.gitignore` ignored the tracked `docs/` sources · P3 · fixed
**Evidence.** `.gitignore` listed `docs` (meaning a documents folder), which matches `docs/`, the Sphinx sources: a new
page there would silently not be added. `docs-computes/docs/test125.claudia(.journal)` were committed although
`docs-*` is ignored, and the Obsidian line ignored plugin files that are tracked on purpose.
**Fix.** `.gitignore` rewritten by topic: `docs/_build` only, `web/dist` added (CODE-02), only Obsidian's per-person
`workspace*.json` ignored. The two test documents and `web/dist` are untracked.

### DOC-01 · Decision numbers are used twice for different decisions · P2 · fixed
**Evidence (measured, project context and `54d1245`).** Two blocks of decision numbers were allocated twice:

| Number | Meaning in `decision-log.md` | Meaning in the E2 / Linux-client notes |
|---|---|---|
| D70 | OpenDocument is the first interchange family | Threat model |
| D71 | Goal, audience and stage are suggestions | Key hierarchy |
| D72 | Material moves between apps through the client | User names are not visible |
| D73 | Styling is CSS in all three apps | Readable without a password |
| D74 | Cut, Copy, Paste in the Edit menu | Primitives: Argon2id, AES-256-GCM |
| D75 | Details of styling | Recovery key |
| D76 | Help system is a knowledge base | Write path (journal, group commit) |
| D77–D82 | creates first draft (shapes, styles, ids, locks) | container package, export, password rules, downloads, names, extension |
| D97–D99 | Windows sandbox, user's own LaTeX, help topic | Layout of native clients, shell contract versioning, local server |

The collision is **live in the source**, not only in documents: `claudia_container/crypto.py` cites D72, D73 and D74
meaning hidden names, the plain manifest and the primitives, while `claudia_server/composes.py` cites D73 and D75
meaning styling-is-CSS and the styling details. The same number means two things two directories apart.
**Why it matters.** The decision log is the project's memory and the thing stories are justified against. A reader who
follows a D-number from a docstring can land on the wrong decision, and any future "this rests on D73" is ambiguous.
**Fixed.** `decision-log.md` keeps the product numbering (it was first and is cited most widely); the E2 block moved
to **D100–D112** and the native-client block to **D113–D119**, with a mapping table in the log so old references
resolve. The code citations are now updated to match: `claudia_container/__init__.py`, `container.py`, `crypto.py`,
`slots.py`, `journal.py`, `passwords.py` and their tests, plus `CHANGELOG.md`; `claudia_server/auth.py`, `sealed.py`
and its test. `claudia-creates` and `claudia-server/composes.py` needed no change — both already cited D73/D75 in
their canonical (post-collision) meaning, styling-is-CSS, not the colliding one.
**Acceptance — met.** `tests/test_decision_log.py` adds two checks: no row in `decision-log.md` is allocated twice,
and every `D<number>` cited anywhere in `packages/`, `clients/`, `web/`, `scripts/`, `tests/`, `docs/` and the root
changelogs resolves to exactly one row (it deliberately excludes `claudiaoffice-log/` itself, which is the log and its
own historical account of the collision).

---

### PROC-04 · CI's Python job fails on every OS · P1 · fixed
**Evidence (2026-11-10, `301ded6`).** Run exactly as `.github/workflows/ci.yml` runs it, `check_debt.py --ci` ends
"FAILED: e2e greeting": the browser test (UX-10) skips where the web app is not built, and the job allowed only the
web and Linux-client skips. No job ran the browser test either.
**Fix.** The Python job allows that skip; the new `e2e` job runs it for real (PROC-06).

### PROC-05 · CI's web type check checks nothing · P2 · fixed
**Evidence.** `web/tsconfig.json` is `files: []` plus references to the generated projects, so `npx vue-tsc --noEmit`
(without `-b`) type-checks no file: with `export const broken: number = "x"` added it still exits 0, while
`npm run typecheck` (`nuxt typecheck`) exits 2. The type error in `Workspace.vue`'s `chartInserted` passed CI this way.
**Fix.** The web job runs `npm run typecheck`, as the gate does.

### PROC-06 · No CI job ran a browser or the Windows client · P2 · fixed
**Evidence.** Neither `tests/e2e` nor any `web/e2e/*.cjs` script ran anywhere, and Playwright was not a declared
dependency of `web/` (CODE-01). All seven scripts failed on `main`: six on selectors from before the connection
indicator and File ▸ Manage existed, one on a toast for formulas "not there yet". Behind them were four real bugs
(UX-16 to UX-19). The Windows client's 63 vitest tests and its menu `--check`, which its own docstring says "a CI job
runs", ran nowhere; one test and the generated menu were broken (CODE-11).
**Fix.** New `e2e` job (Chromium; `tests/e2e`, then the five scripts against `./start.sh all`, then the two that start
their own server; screenshots kept on failure) and `windows-client` job (vitest, `tsc`, menu `--check`, the tool's
pytest). The scripts were brought up to date and all pass.

### PROC-07 · A performance guard measures the garbage collector · P3 · fixed
**Evidence.** `test_opening_from_a_snapshot_is_linear_in_the_formulas` failed with 25.07x against its 25x bound.
Measured: 800 → 8,000 formulas takes 20–25x with the cyclic collector on and 11x with it off — a collection is
triggered by how much is allocated, so it lands in the large case.
**Fix.** Both timing helpers (`claudia-core`, `claudia-computes`) hold the collector off while timing, as `timeit`
does.

### PROC-08 · A test of the gate fails wherever `npm install` was run · P3 · fixed
**Evidence.** `test_ci_catches_the_real_bug_with_no_node_modules` asserted that *this checkout* has no
`web/node_modules`, so it failed on every developer machine and passed only in CI.
**Fix.** `web_checks()` takes the web folder; the test points it at an empty one.

### PROC-09 · Two branches both released claudia-core 0.13.0 · P1 · fixed 2026-11-12
`ai_server` added `Document.scratch` as 0.13.0 while `styling-suite` had released 0.13.0 and 0.14.0; the merge kept
both 0.13.0 headers and `_version.py` at 0.14.0, so `test_changelog_versions.py` failed the gate. Renumbered the
scratch release 0.15.0, raised `_version.py`, regenerated `tests/api/claudia_core.json`, fixed the reference in the
E7.8 story. **Prevention:** the version is the last thing a branch sets, after merging `main` (CONTRIBUTING).

### PROC-10 · The Sphinx build fails on three unresolved types · P1 · fixed 2026-11-12
`ModelEngine`'s signature names `model_engine.Budget` and `lens.Lens` (and `Lens.recorder` names `lens.Recorder`);
none was in `docs/api/claudia_server.rst`, and `nitpicky` turns that into an error. Added the three under
"Assistant".

### PROC-11 · The LibreOffice check broke silently · P2 · fixed 2026-11-12
`scripts/odf_libreoffice_check.py` built its deck by hand and gave a shape's words the outline style `plain-shape`;
since D310/D316 an outline cannot style words, so `new_deck()` raised. Its CI job is `continue-on-error` and nothing
else ran the script, so nothing turned red. It now takes the styles the server gives a new object
(`STYLE_OF_KIND`, `PARAGRAPH_STYLE_OF_KIND`), and `tests/test_odf_libreoffice_check.py` builds the three new files and
every library case in the normal suite, without LibreOffice. Verified with LibreOffice 24.2: 31 of 31 read.

### PROC-12 · The Linux client's end-to-end test reads the address too early · P1 · fixed 2026-11-12
Since the page cache is emptied before every load (`WebPage._load_current`, asynchronous, commit 08ffcb9) the window
shows the web view before the view has an address, and `view.get_uri()` is `None` for a moment. The test now waits for
the address. 558 passed, 6 skipped under `xvfb-run` on Python 3.12 with GTK 4 and WebKitGTK 6.0.

### PROC-13 · Nothing pinned Python 3.14 · P2 · fixed 2026-11-12
`requires-python = ">=3.14"` lets `uv` take the newest Python it finds; with 3.15 on a machine the environment was
made with it, and `openvino-genai` has only cp314 wheels and no sdist in `uv.lock`, so `--ai` could not be installed.
`.python-version` (`3.14`) now decides, and `tests/test_python_version.py` keeps it, every `requires-python`, the CI
workflows, the Dockerfile and `build-deb.sh` on the same version.

### PROC-14 · Two browser scripts fail on `main` · P2 · fixed 2026-11-12
`web/e2e/styling.cjs` read the gallery's font weight from `.name`; the look moved to `.name .look`. `demo.cjs` failed
on UX-20. All seven scripts and `tests/e2e` pass against `./start.sh all` (Chrome for Testing 153).

### PROC-16 · The undo guard measured one sample and failed now and then · P3 · fixed 2026-11-12
`test_undoing_the_latest_step_does_not_depend_on_the_history_before_it` (claudia-core perf) timed a single run of 50
undos and failed once in this round at 4.04x against a 4.0x limit (0 of 15 reruns). Undo uses up its steps, so it could
not repeat on one document; it now takes the best of three fresh documents per size. Same kind as PROC-07.

### PROC-15 · The tracker and the backlog lag the code · P2 · new, partly fixed
**Evidence.** In this file PERF-01, PERF-05, UX-01, UX-03 and UX-05 were "verified open" although fixed in the tree
(corrected above). In the backlog, E7.7 is `todo`, 0 % with a "Built 2026-11-11" paragraph; 64 of 90 stories that are
`in-progress` sit at exactly 50 %, which the README calls "an estimate from the code, not from hope" — 50 is a
placeholder. **Fix.** A branch that fixes a tracked item changes its row in the same commit (CONTRIBUTING rule);
`test_backlog.py` could refuse `progress: 50` on a story without a status-evidence paragraph.

### CODE-13 · `WorkerPool` has no callers · P2 · fixed 2026-11-19
**Evidence (read).** `workers.py` (E3.5) says it exists for PERF-02 and D37, `Hub` makes one and stops it, but nothing
in `packages/*/src` calls `submit`. Meanwhile every edit still `fsync`s on the event loop (PERF-02) and threshold
packing runs there (PERF-06). **Fix.** Either use it — journal append and packing via `asyncio.to_thread` (I/O, a thread
is enough), formula recalculation of large structure edits via the pool (PERF-07, E4.4) — or remove it until a caller
exists. **Acceptance.** A test that a slow `fsync` (monkeypatched to sleep 50 ms) on one document does not delay a
`cells` request on another.
**Re-checked 2026-11-20 at `f34365f`.** `app.py` sends every import to `hub.workers` (since 2026-11-16) and
`heavy_dispatch.py` sends a formula's heavy call (D1314, salvaged from `worker-pool` on 2026-11-19). Nothing in the
library is heavy yet, and the what-if outcomes still run on the loop: PERF-10. Timeouts and a memory cap are SEC-19.

### CODE-14 · The Windows and macOS shells are one design kept as two copies · P2 · fixed 2026-11-15
**Evidence (read, `d696927`).** At `7e619a2` the Windows shell (7 files, 975 lines) had none of macOS's connection,
trust or server list. The branch `win-client-complete` (merged as `d696927`) rebuilt it on the macOS design, which
closes that feature gap, by copying: `clients/windows/src` and `clients/macos/src` now have the same 22 file names,
11 of them byte-identical (bridge, connection, connector, contract, core, core-entry, core-protocol, extension,
servers, settings, shell-page-entry: about 1,550 lines) and the rest differing only where the OS does
(paths, launch, server, menu). Every fix to the shared part now has to be made twice, and nothing checks that it is.
**Recommendation:** move the identical files into one `clients/neutralino/` package (or `clients/shared/`) that both
build from, keeping per-OS `paths`, `launch`, `server`, `menu`; until then, a test that the shared files stay
byte-identical, so a fix in one copy fails the build until it is in the other.
**Re-checked at `7994b00` (2026-11-15, measured):** 11 of 22 source files byte-identical (1,658 lines), 10 test files
identical (1,233 lines), and the two `tools/generate_menu.py` copies write byte-identical `src/generated/menu.*.json`.
Still nothing checks the copies stay equal. Merging them needs D113 ("one package per OS") amended: asked in
`notes/code-review-2026-11-15.md`.
**Fixed (2026-11-15, D660, superseding D113):** one package, `clients/neutralino/`. Everything is shared but
`src/platform/` (folders, interpreter, binary and window start, dialogs, menu and shortcuts, ending a process tree),
behind `HostPlatform` and `PagePlatform`; each bundle is made for one platform (`build:macos`, `build:windows`). The
platform tests run for both systems on any host, so the Linux CI checks the Windows code too; one
`tools/generate_menu.py` writes the menus once. The macOS client gained the Windows client's `bin/` scripts; the
Windows window now closes through the page, as on macOS (to be tried on a real Windows machine).

### CODE-15 · `./start.sh` folder layout · P2 · fixed 2026-11-12
**Evidence.** Documents in `<repo>/docs-<app>` (before 2938f0a: `demo-docs`, `demo-docs-<app>` — the folders people
still find), `--dir X` meaning X for one app but `X/<app>` for `all`, and no `--state-dir`, so the three dev servers
shared one certificate and one administrator list in `~/.local/share/claudia`, the tree where the Linux desktop app
keeps `~/.local/share/claudia/<app>/documents`. **Fix (agreed 2026-11-12).** `.claudia/<app>/documents` and
`.claudia/<app>/state` per checkout (ignored); `--dir DIR` means `DIR/<app>/…` always; old folders are named at start,
never moved. Not changed: the server's own default state folder on Windows is `%APPDATA%` (roaming) while the Windows
shell uses `%LOCALAPPDATA%`; and every server puts a `docs/` folder inside `--dir`, one level more than anybody expects.

### UX-24 · A named style could not be applied to another text box from where people look for it · P1 · fixed 2026-11-12
**Evidence (measured, `e56e8f9`, owner's report).** Restyle a text box, name the new style "Callout", select another
text box: right-click ▸ Style… or Format ▸ Edit this style… opens the style popover, and clicking "Callout" there only
*shows* its look (UX-14, as in composes) — nothing is applied, and a click on B next changes Callout everywhere. The
only working way was Format ▸ Apply style ▸, which nobody found, because composes ("Body text ▾") and computes
("Style ▾") have a picker in their bar and creates had none. **Fix (agreed).** `StylePicker` in creates' insert bar
(`InsertBar.vue` has a slot for it, `SlideWorkspace.vue`): the selected object's main slot (a text box's words, a
shape's outline, a picture's box), and a second picker "Label" for a shape's words (`objectStyleHost(styling,
'label')`). The popover stays preview-only, consistent with the other apps. **Test:** `web/e2e/creates-styles.cjs`
(the reported case, a shape's two pickers, the counts of UX-25).

### UX-25 · All styles… counted uses with the selection's noun · P3 · fixed 2026-11-12
"Body text … 1 shape" (used by a text box) whenever a shape was selected: `StylesDialog` used `host.noun` for every
row. `StyleHost.usesNoun` ("object" for an object host) now names what the counts count.

### UX-26 · The AI mode switch · P2 · fixed 2026-11-12
**Evidence (owner's report, measured).** The segmented control used the page's `--text`, ink, on the always-dark
panel: with *suggest* chosen, "Act at once" was ink on ink in the light theme. And it sat inside the chat section.
**Fix.** Directly above the History & Chat | Help tabs, in the panel's own light inks (unchosen half ≥ 4.5:1, checked
by `demo.cjs`), a real radio group (arrow keys, one tab stop).

### UX-27 · A new object lands exactly on the previous one · P3 · new, open
**Evidence (measured).** Text ▸ Text puts the second text box on the first; the browser scripts move them apart by
dragging. **Fix.** Offset each new object by one grid step (or place it in the first free spot) when another object
sits exactly there.

### UX-28 · The page declares no language · P2 · fixed on `bitv`, awaiting commit
**Evidence (read, 2026-11-13).** No `lang` on `<html>`: `nuxt.config.ts` set none and nothing in `web/app` did, so a screen
reader chose its voice by guesswork, for a UI that is German or English (WCAG 3.1.1, level A). **Fix.** `lang="en"` in the
build, and `useI18n` declares the language once its catalog has loaded (`languageOf`, `setPageLanguage` in
`web/app/lib/i18n.ts`): a German browser whose catalog did not load stays `en`, because that is what is on the screen.
The open dialog and the admin pages are English only; `app.vue` puts `en` back when a document is left. **Test:**
`web/tests/i18n.test.ts`; `web/e2e/regions.cjs` checks `en`, and a `de-DE` browser was checked by hand to give `de`.

### UX-29 · A keyboard user cannot leave the grid · P2 · fixed on `bitv`, awaiting commit
**Evidence (read, 2026-11-13).** `SheetGrid.vue`'s `onKey` takes Tab and Shift+Tab for stepping between cells and
`preventDefault`s them, and nothing else moved focus out (WCAG 2.1.2 no keyboard trap, 2.4.1 bypass blocks). **Fix.** F6 and
Shift+F6 go to the next and previous part of the window (menus, toolbar, document, panel, footer; hidden or empty parts
are skipped; wrapping round), in all three apps, and from the formula bar. `web/app/lib/regions.ts` (`cycleRegions`),
`regionShortcuts` in `shortcuts.ts`, wired once in `DocumentFrame.vue`; parts are marked `data-region`. Listed in
Config ▸ Shortcuts. **Test:** `web/tests/regions.test.ts`, `shortcuts.test.ts`, `web/e2e/regions.cjs` (Chrome only).
**Left.** F6 does not work while a cell is being edited in the grid (the editor keeps its keys: finish with Enter or Esc);
in a browser tab F6 may also be claimed by the browser (Firefox not tried); no menu item carries it.

### UX-30 · The tab title does not name the document · P3 · fixed on `bitv`, awaiting commit
Every tab of one app read "Claudia Computes" (WCAG 2.4.2). `tabTitle(app, documentName)` now gives
"budget 2027 – Claudia Computes". **Test:** `web/tests/shell-bridge.test.ts`, `regions.cjs`.

### UX-31 · Pictures, charts and shapes had no description of their own · P2 · fixed on `bitv`, awaiting commit
**Evidence.** An image had its alt text only from the import (and the import dialog of the sheet insisted on one); a shape,
a text box and a chart had none; nothing said that an object is only decoration, so a screen reader read "image" for
every flourish (WCAG 1.1.1, BITV 1.1.1 Nicht-Text-Inhalte).
**Fix.** Every object has `description` and `decorative` (`claudia_core.ObjectBody`, command schema 2 with an upcaster, so
old documents replay), a new undoable command `DescribeObject`, and the server method `describe_object` in computes and
creates (composes has no objects yet). A picture still needs words or the decorative mark; for anything else a description
is optional. Format ▸ Describe Object… (Ctrl+Alt+D, `format.describe`, also on the Windows/macOS menus) and the object's
context menu on a slide ("Describe…") open one dialog with a 300-character counter and a "Decorative" box; the import
dialogs have the box too. The accessible name of an object is its kind plus its description ("Picture: …", "Picture
(decorative)", "Picture (no description)"); a decoration is `role="presentation"` and hidden. Ctrl+Alt+PageDown/PageUp step
through the objects of a sheet, which only the mouse reached. A chart tab is named by its chart.
**Export.** PPTX: `descr` on `p:cNvPr` and the decorative extension (`adec:decorative`, from memory of the 2017 extension:
**verify in PowerPoint**). ODP: `svg:desc`; ODF 1.3 has no attribute for decorative, so the export reports a loss
(`odp_export_losses`). ODS and XLSX write no floating objects yet. Import of descriptions from those files is not built.
**Test:** `packages/claudia-core/tests/test_object_description.py`, `claudia-creates/tests/test_descriptions.py`, the server
tests of both apps, `claudia-creates-io` pptx/odp tests, `web/tests/descriptions.test.ts`, `object-menu.test.ts`,
`object-cycle.test.ts`, `clients/linux/tests/test_manifest.py`, `web/e2e/describe.cjs`, `describe-creates.cjs`.
**Design to confirm:** `notes/mockups/describe-object-and-grid-structure.svg` (built before it was agreed).

### UX-32 · The workspace pages have no landmarks · P3 · new, open
axe (best-practice rules, not WCAG ones) finds no `main` landmark and content outside any landmark on the computes page.
F6 and the skip link (UX-29) are the bypass the page has; landmarks would give screen readers the same jump list: `header`
for the menu and toolbar, `main` for the document, `complementary` for the panel, `contentinfo` for the footer. Needs a look at
how `DocumentFrame.vue` is laid out in all three apps before touching it.

### PROC-17 · `demo.cjs` fails once the client sends *suggest* · P2 · fixed 2026-11-12
The switch (E7.7) made every client send *suggest* by default; computes cannot propose yet, so `@ai build an example
budget` was refused and the script waited for "Done." in vain. It now chooses "Act at once" first and checks the switch.

### CODE-16 · The macOS client's generated creates menu was stale · P2 · fixed 2026-11-12
`clients/macos/src/generated/menu.creates.json` had no Format ▸ Apply Style… (the Linux manifest has had it); the
Windows job runs `generate_menu.py --all --check`, but no job does that for macOS. Regenerated with this round's menu
changes, and the `windows-client` job now runs the same `--check` for `clients/macos` (Python, no Mac needed).

## Round of 2026-11-13 at `cfa2d91`

### SEC-18 · A search pattern the static guard lets through freezes the whole server · P1 · fixed 2026-11-13
**Evidence (measured).** `claudia_core.search` refuses patterns that "could backtrack without end" by looking at their
shape (`_backtracks`), because Python's `re` cannot be interrupted. Two shapes pass it and are exponential: `(a|a?)+!`
takes 12.5 s on 24 characters, `(x\w*)*!` 1.2 s, each doubling with every further character (`(\w|\d)+!` and
`(.|\s)*!` pass too, Python happens to optimise them). `search_find` checks its 2 s budget *between* cells, and every
method runs synchronously on the event loop, so one request from anybody who can open a document stops every document on
that server for minutes. The AI user searches through the same methods (D261). D284 asked for "a time budget in the worker
pool"; the as-built note replaced it with the guard.
**Fix (to agree, see the recommendations).** Make the search interruptible instead of making the guard longer: either
the `regex` package with its `timeout=` (also gives `\p{L}`; D287 is still open for exactly this), or the search in the
`WorkerPool` (CODE-13) with a hard deadline that kills the worker. Keep the guard as a quick early answer while typing.
**Test:** `packages/claudia-core/tests/test_search.py::test_a_pattern_the_guard_lets_through_still_cannot_hold_the_server`
(strict `xfail` until fixed; remove the mark with the fix). Add a server test that `/api/health` answers while a search
runs.
**Fixed (D288).** The engine moved to the new package claudia-search and runs patterns on `regex` with a deadline inside
the pattern (`re` still reads them, so syntax and messages are unchanged); the shape guard is gone. One deadline per
request, 2 s. Measured: `(a|a?)+!` and `(x\w*)*!` now finish at once on 10,000 characters; `(?:a|aa)+!`, which `regex`
cannot shortcut, stops at its deadline. **Tests:** `claudia-search/tests/test_engine.py` (every former freezer within
its deadline, every method keeps it, the default limit), `test_scan.py`, and in the server
`test_a_pattern_that_could_run_forever_stops_at_the_deadline_and_says_so`.

### PERF-09 · Making a webfont blocked every request of every document for seconds · P2 · fixed 2026-11-13
**Evidence (measured).** `GET /api/fonts/{sha256}.woff2` made the WOFF2 file on first use inside an `async` handler:
2.4 s for DejaVu Sans (740 KB), 37 s for a 10 MB font. A page asks for several fonts on first load after a deploy.
**Fix.** The route is a plain function, so FastAPI runs it in its thread pool (`claudia_server/fonts.py`). **Test:**
`test_server_fonts.py::test_making_a_webfont_does_not_hold_up_the_rest_of_the_server`.

### PERF-10 · What-if outcomes are recalculated on the event loop · P2 · new, open
**Evidence (measured).** Three inputs with 30 alternatives each and 1,000 formulas reading them: every edit of an input
*or of any of the 1,000 dependent cells* takes 9.0–9.5 s (`outcomes.py`: 27,000 combinations, sampled to 2,000 ×
1,000 cells, `MAX_WORK = 2_000_000`). An edit elsewhere costs 1 ms. The calculation is synchronous inside the command, so
the server answers nobody for those seconds.
**Fix.** Apply the edit and answer at once with the first alternatives' values; compute the summaries in the worker
pool (CODE-13) and send them as their own event (`outcomes` with the revision they belong to; a newer revision cancels an
older run). Then lower `MAX_WORK` for the synchronous path to what fits in ~50 ms, or drop it. **Test:** a server test
with the model above that an edit is answered in < 200 ms and the outcomes event follows.

### PERF-11 · Search preview and replace have no time budget · P3 · fixed 2026-11-13
`_plan` (`search_preview`, `search_replace`) scans the whole scope with no deadline; only `search_find` has one. With
SEC-18 fixed this is linear, but a large workbook still holds the loop. **Fix:** the same budget, or the same worker.
**Fixed.** The same deadline: `search_preview` answers `timed_out`, `search_replace` refuses (`command_error`) rather
than replace part of it. **Test:** `test_a_preview_that_ran_out_of_time_says_so_and_a_replace_refuses`.

### UX-33 · A new document starts with an undoable step · P2 · fixed 2026-11-13
**Evidence (measured, screenshots).** In a new workbook Edit's first item is "Undo Add sheet"; Ctrl+Z leaves "This
document has no sheet yet." In a new text or deck it is "Undo Language" (D915: the maker's client sets the language right
after creating). A person's first Ctrl+Z undoes something she never did. It also broke the Linux client's end-to-end
test (PROC-20).
**Fix.** Make the first sheet and the starting language part of creating the document (a `create` parameter, or a
setup step the log marks as not undoable), not a command in the person's undo stack. **Test:** per app, a new document
has nothing to undo; a browser script presses Ctrl+Z in a new workbook and still sees Sheet1.
**Fixed (D362).** The server runs the app's `setup_commands` once when it creates a document, as one `core.Setup` entry
by its maker that is never an undo step (claudia-core 0.20.0): computes adds Sheet1, composes and creates set the
language from the `locale` of `hello`. The web client no longer does either. **Tests:**
`claudia-server/tests/test_server_setup.py`, the Linux client's end-to-end test (Undo off in a new text again),
`web/e2e/keys.cjs` (Ctrl+Z in a new workbook keeps Sheet1; Undo disabled in a new text).

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

### UX-35 · Menu entries without a shortcut · P2 · fixed 2026-11-13
**Evidence (measured).** The project rule is that every menu entry has a key shortcut. In the shared manifest 30
(composes), 37 (computes) and 33 (creates) entries have none. Part of that is display only: Save, Undo, Redo, Copy, Cut,
Paste are handled by the page and therefore not bound natively (`test_keys_the_page_handles_itself_are_not_bound_a_second_time`),
so the GNOME menu shows no key for them. Truly without a key: New, Open, Save New Checkpoint, Download, Manage ▸ (6),
Close, Paste As ▸ Plain Text, Apply Style, All Styles, Colours, the View toggles, Ask the Assistant, Help ▸ (4),
computes' New Sheet, Row ▸, Column ▸, Clear Cells, Image, Chart, Names, SQL; creates' New Slide, Text Box, shapes.
**Fix.** Designer: one key table for the three apps (GNOME HIG first: Ctrl+N, Ctrl+O, Ctrl+W, Ctrl+Shift+S, F1, F10…),
with an explicit, short list of exemptions (the language picker). Shell: show the page's keys in the native menu with
GMenu's `accel` attribute (display only, no binding). **Test:** a manifest test "every action has an accelerator or is
on the exemption list", and the same over the web menus.
**Fixed (D360).** One key table for every app and client in the manifest; `scripts/generate_keys.py` writes the web's
copy and the table for people (`notes/keyboard-shortcuts.md`). The page listens for every key in every client (its menu
entries run as if clicked); GTK binds only the shell's own (Quit, About, Shift+F10) and shows the rest with `accel`; the
Windows menu shows every key. **Tests:** `test_every_menu_entry_has_a_key_but_the_language_names`,
`test_one_action_has_one_key_in_every_app`, `test_only_the_shells_own_keys_are_bound_natively`,
`test_no_key_is_one_a_browser_keeps_or_alt_gr_types`, `tests/test_keys_generated.py`, `web/tests/shortcuts.test.ts`,
`web/e2e/keys.cjs`. **Left:** a Mac variant (Cmd+M is Minimize, Cmd+Option+H Hide Others), D122's per-OS sets.

### UX-36 · Features of this round are missing from the native desktop menus · P2 · fixed 2026-11-13
**Evidence (measured: web menu ids against `manifest.for_app`).** The desktop shells hide the web menu bar and show the
manifest's menu instead, so these are not in the desktop menus: File ▸ Print… (composes, creates), Format ▸ Bulleted /
Numbered List, Edit ▸ Soft Hyphen, Non-breaking Hyphen (composes); Edit ▸ Image…, Chart…, Format ▸ Clear Cell Style,
Tools ▸ Names…, SQL… (computes); Edit ▸ Image…, View ▸ Grid (creates). Some are reachable by toolbar or key, Print only by
Ctrl+P. The project rule "check whether the desktop clients need adapting" was not caught by any test, because the
existing test checks only the other direction (native ids exist in the web source).
**Fix.** Add the actions to `manifest.py`, regenerate the Windows and macOS menus, translate. **Test:** the reverse
check: every web menu `id` of an app is in its manifest, or on a named list of web-only items with the reason.
**Fixed (D361).** All added, regenerated and translated; also Format ▸ List ▸ (every app) and composes' Edit ▸ Insert ▸
for the two hyphens, which had keys and no entry. **Test:** `test_every_web_menu_entry_is_in_the_desktop_menus_too`.

### UX-37 · composes shows an act/suggest switch that changes nothing · P3 · fixed 2026-11-16
The switch is live in composes and says beneath it "Text documents: the AI suggests either way." A control that does
nothing should not be offered. **Fix:** show the line in place of the switch (or disable it), the same component as
UX-34 (b).
**Re-checked 2026-11-20 at `f34365f`.** The line "Text documents: the AI suggests either way." went with `b66fae0`
(composes gets its AI, D640, D680, D681): in composes *suggest* proposes with `suggest`/`suggest_words` and *act*
writes.

### UX-38 · Dialogs are stretched to the window's height in the Linux client · P2 · fixed 2026-11-14
Reported by the owner on the recovery-key dialog (2026-11-14): oversized round buttons, big gaps, a dialog as tall as the
window. **Measured** in the web inspector of the Linux client (WebKitGTK 2.52.3): the `<dialog>` was exactly its
`max-height` (742 px) with 456 px of content, every auto row of its grid stretched (`lead` 148 px for 80, `buttons`
82 px for 35). `max-height: none`, `height: fit-content` and `height: max-content` changed nothing; `align-content: start`
brought it to 456 px, and so did docking the inspector (a shorter window), which is why it "snapped into position".
Firefox does not do it. **Fix:** `Modal.vue` says `height: fit-content`, `align-content: start`,
`grid-auto-rows: max-content`; the dialogs' own `.buttons` rows need no change. **Test:** `web/tests/modal-layout.test.ts`
reads the stylesheet (the stretching only happens in WebKitGTK, which no test here runs); a measuring check in WebKitGTK
itself would need the Linux client under Xvfb in CI.

### UX-39 · A dialog or the search panel cannot be moved; the panel's help link did not reach its topic · P2 · fixed 2026-11-15
Reported by the owner on the composes panel (2026-11-15). **Read:** neither `Modal.vue` nor `SearchPanel.vue` had any
moving, and the log had no decision for it. The panel's ⋯ ▸ "About searching and patterns" opened the Help tab at the
how-to list, under the panel, and the Help panel drew a topic's Markdown as typed (`**`, `##`, a line break in every
sentence). Also on the panel: "in x texts", five switches that filled it, links for what are the main actions.
**Fix:** D520 (moving, `lib/dragging.ts`, `lib/use-draggable.ts`), D521 (the panel's quick path), D522 (Markdown in help
topics, the topic opened by `SearchHost.helpTopic`). **Tests:** `dragging.test.ts` (where a box may go; the keys),
`help-markdown.test.ts`, `search-panel-wording.test.ts` (the Look-in line and the match line), the hosts' tests for
`helpTopic`; the component wiring was run in a headless Chrome page only, not in `e2e/` (see the implementation note).

### PROC-18 · The gate fails on every fresh clone · P1 · fixed 2026-11-13
`tests/test_notes_claim_built_files.py` read `web/public/wasm` in `notes/e9-print-and-layout.md` as a claim about the
tree; that folder is made by `npm run build`, so CI's Python job (no build) failed on all three OSes. The check now
skips paths `.gitignore` names (build output). **Test:** `test_a_build_output_named_in_gitignore_is_not_expected_in_a_fresh_checkout`.

### PROC-19 · Browser scripts and a client that CI never ran · P2 · fixed 2026-11-13
`e2e:lists`, `e2e:regions`, `e2e:grid-a11y`, `e2e:describe`, `e2e:describe-creates` and `e2e:macos-shell` were in
`web/package.json` and in no workflow; the macOS client's vitest, type check and build ran nowhere; `docker.yml` and
`deb.yml` did not run for a change in `layout/`, which the web app links. All added (all 18 scripts pass locally in CI's
order). **Test:** `tests/test_ci_workflow.py`.

### PROC-20 · Two end-to-end tests on `main` fail · P1 · fixed 2026-11-13
`demo.cjs` counted the grid's empty active cell (`.cell.blank`, drawn for `aria-activedescendant`, UX-02) as a cell; the
Linux client's test asserted that a new text has nothing to undo, which D915 changed (UX-33). CI's `e2e` and
`linux-client` jobs were red at `cfa2d91`. Both tests corrected.

### PROC-21 · The demo deployment checked the wrong domain · P2 · fixed 2026-11-13
`deploy-demo.yml` defaulted `DEMO_URL` to `demo.claudiaoffice.de`; the domain is `claudia-office.de`. Without the
repository variable set, the last step failed after a good deployment (or checked somebody else's host).

### PROC-22 · The LibreOffice job may still fail silently · P3 · new, open
`odf-libreoffice` is `continue-on-error` "until it has a track record". It has read 31 of 31 files in every round since
PROC-11. **Fix:** make it blocking; pin the LibreOffice version in the log line so a distribution update is visible.

### CODE-17 · Three names for "use this browser" · P3 · new, open
`tests/e2e` reads `CLAUDIA_CHROMIUM`, five `web/e2e` scripts `CHROME`, five `CHROMIUM`, the rest nothing. **Fix:** one
`web/e2e/browser.cjs` (`launch()` reading `CLAUDIA_CHROMIUM`, with `--no-sandbox` where needed) used by every script.

### CODE-18 · The search "for all three apps" speaks only in sheets · P2 · fixed 2026-11-13
`SearchPanel.vue` says it is one panel for all apps (D284), but matches, `leave`, `skipped` and `left_out` are
`{sheet, row, col}` in the panel, in `session.ts` and in the protocol. Composes (paragraph, offset) and creates (slide,
object) will not fit. **Fix before search reaches composes:** an opaque `where` (a key and a label from the host) in the
panel and the protocol; computes maps it to its cells. Discuss first: it changes the method signatures (API version).
**Fixed (D289).** Every answer names its place as `at` (`{sheet, row, col}` in a workbook), `leave` is `{at, match}`; the
search over a document's texts is app-neutral (`claudia_search.scan`, `plan`); the web panel reads places only through
its host (`keyOf`, `where`, `jump`, `scopeLabel`). Left: the panel's words ("Whole cell") and kinds are computes'.
**Tests:** `claudia-search/tests/test_scan.py` (places that are not cells), the server's
`test_every_answer_names_a_cell_by_its_at` and `test_leave_takes_only_cells_it_can_read`, `web/tests/sheet-search-host.test.ts`.

### CODE-19 · Debugging code left in the journal · P3 · new, open
`claudia_container/journal.py` keeps `_open_in_this_process` (scans every object of the garbage collector) from the
Windows CI hunt, and `_replace` sleeps up to ~10 s on Windows on the event loop (with PERF-02). The CI cause was
Controlled Folder Access. **Fix:** drop the diagnostic; move the retry off the loop with PERF-02.

### CODE-20 · The image's build tool is not pinned · P3 · new, open
`COPY --from=ghcr.io/astral-sh/uv:latest`: a new uv can change the image without a commit. **Fix:** pin a version (and
digest), updated by Dependabot.

### CODE-21 · One module for every computes method · P3 · new, open
`claudia_server/computes.py` is 1,228 lines: cells, names, SQL, styles, images, charts, random numbers, outcomes, search.
composes already split its lists out (`composes_lists.py`). **Fix:** one module per feature, registered on the same table.

### DOC-02 · Stale launcher name · P3 · fixed 2026-11-13
`start-client.sh` became `start-linux-client.sh` (148610e); `clients/linux/README.md`, the script's own usage text and
the macOS and Windows launchers' comments still named the old file. Changelogs and dated notes keep the old name.

### CODE-22 · xlsx from today's Excel: the import failed, an edit dropped what openpyxl does not know · P2 · fixed 2026-11-13
**Evidence (measured)** on two real workbooks the owner supplied (kept out of the repository): `xlsx_to_workbook`
failed on a planning model with `'ArrayFormula' object has no attribute 'strip'` (openpyxl hands an array formula
over as an object); on a classroom game, editing one cell and saving removed the sheet's list of choices from another
sheet (`x14:dataValidation`), and on the planning model the same save path drops the spill marks (`cm`), icon sets
(`x14:cfRule`) and a picture in a cell (`vm`) of the edited sheet. Formulas with functions Excel added after 2007 were
written without `_xlfn.`, so Excel showed `#NAME?`.
**Fix.** D370 (read from the XML, never fail, a formula the model cannot calculate comes in as Excel's value) and D371
(write the edited cells into the original sheet's XML). Tests first: `packages/claudia-computes-io/tests/test_xlsx_real_world.py`
and `test-documents/xlsx/beyond-claudia/excel-today`.

## Round of 2026-11-15 at `078d19d`

All of the day's branches merged (clients, search-ui, file-handling, dock, containers). The report is
`implementation-notes/qa-2026-11-15.md`; the Python gate, the web, layout and client unit tests were clean at
`078d19d`, so everything below was found by running the end-to-end tests and by reading.

### UX-40 · The first slide of a new presentation had no name · P2 · fixed 2026-11-15
**Evidence (measured)** with the new `tests/e2e/test_things_have_names.py`: the slide an empty presentation starts with
is part of the empty model, so no `add_slide` named it (D550); the next slide got the first free name, "Slide 1", and
the tab of the unnamed one says "Slide 1" by its place. **Fix:** the server names what an empty document holds in the
same `Setup` entry that sets its language, in the maker's language (`thing_names.naming_steps`, `app._set_up`). Test
first: `test_server_setup.py::test_a_new_decks_first_slide_has_a_name_in_its_makers_language`; in the browser,
`web/e2e/dock.cjs`.

### UX-41 · Paragraphs of a text could not be tagged · P2 · fixed 2026-11-15
Reported by the owner. **Fix (D554):** a paragraph is a thing (`TextModel.block_names`, state schema 11; kinds
`heading`, `item`, `paragraph`), named when first pointed at (`name_thing`); `#` offers the named paragraphs, the
headings and the caret's paragraph; Edit ▸ Reference in Chat tags the caret's paragraph.

### UX-42 · A document cannot be renamed · P2 · decided, open
Reported by the owner: Details… says "The name is sealed into the file and cannot change". **Read:** D533 binds every
sealed part, every person's key slot included, to `name:uid`. **Decided (D536):** bind to the uid alone; the owner
renames; clients keep the uid. Build: E5.21.

### UX-43 · A fenced text box becomes a container in two steps · P3 · open
**Read:** `slide-session.ts` `fenceToContainer` adds the container and then removes the box: two entries in the
history (one undo brings the box back next to the container) and the container gets a new default name, so a tag to the
box shows it as gone. **Fix:** one server request that replaces the box in one `Batch`, giving the container the box's
name.

### CODE-23 · The neutralino shells' menus were stale · P2 · fixed 2026-11-15
**Evidence (measured):** `tools/generate_menu.py --all --check` failed in `clients/windows` and `clients/macos`: the
containers merge added Insert ▸ Container (LaTeX, Mermaid, Typst) to the manifest and nobody regenerated, so CI's
`windows-client` job is red on `main`. **Fix:** regenerated; `scripts/check_debt.py` now runs the check as `menus
windows` and `menus macos`, so the gate on a laptop says it before a push (`tests/test_check_debt.py`).

### CODE-24 · `add_object` failed inside on kinds it cannot make · P3 · fixed 2026-11-15
**Evidence (measured):** `add_object` with `kind: "rendered"` (or `"diagram"`) passed the check against
`OBJECT_KINDS` and failed with a `KeyError` on the style of the kind. **Fix:** only text and shape are made there; the
others are refused with where they come from. Test: `test_server_creates.py`.

### CODE-25 · Object names are lost in pptx and odp without a word · P2 · open
**Evidence (measured):** renaming a slide and exporting reports `not-written: names`; renaming an object reports
nothing, because the `objects` facet counts as written. **Fix:** write the names (`p:cNvPr/@name`, `draw:name`; and the
slide names: `p:cSld/@name`, the page's `draw:name`), read them on import (suffixing duplicates), then drop `names` from
the unwritten facets. Until then every presentation's export lists `names` as not written.

### PROC-23 · The browser tests on `main` were red after the dock merge · P1 · fixed 2026-11-15
**Evidence (measured)** against servers started as CI starts them: `demo.cjs` and `composes.cjs` looked for the chat box
as an `input`, which `ChatInput.vue` (a `contenteditable` combobox) replaced; `keys.cjs` expected creates' View menu
without Replay History…. `details.cjs` (D530) was never run anywhere but on the branch. **Fix:** the selectors and the
expected menu; `e2e:details` and the new `e2e:dock` are npm scripts and CI steps. All other web e2e scripts, the
Windows and macOS shell scripts and `tests/e2e` passed.

### DOC-03 · The decision log contradicts itself in places · P3 · fixed 2026-11-17
**Read:** current decisions that later current ones overrule without a supersession: D2 (each app its own doc server,
a GTK client) against D430, D445, D42, D156; D84 (a server hosts one app) against D430; D115 (a new port at every start)
against D504; D44 (File, Edit, Tools, Help) against D120; D242 (checked from `/api/docs`) against D444. `ranges.md`
listed D300–D319 twice. `_rounds.md` had no entry for the file-handling, dock and containers rounds. **Fixed:** the
`ranges.md` row, the rounds, stale lines in two implementation notes and a stale comment in the Windows client.
**Needs a decision:** whether to mark D2, D44, D84, D115 and D242 superseded (proposed: D84 by D430, D115 by D504, D44
by D120; D2 and D242 partly, with a sentence each).
**Fixed 2026-11-17** in the log audit, the code being the truth: D44, D84 and D115 are superseded as proposed, D2 and D242
carry a sentence each (`implementation-notes/log-audit-2026-11-17.md`).

## Reported 2026-11-15, after `078d19d`

### CODE-26 · Closing a window crashes the macOS app · P1 · fixed 2026-11-15
Reported by the owner with a crash report (macOS 27.2, MacBook Air M1): every click on a window's close button ends
claudia-composes with `EXC_BREAKPOINT (SIGTRAP)`, "BUG IN CLIENT OF LIBDISPATCH: dispatch_sync called on queue already
owned by current thread". **Read** (the crash's stack against Neutralino's v6.8.0 source): `windowShouldClose:` in
`lib/webview/webview.h` → `windowStateChange(WEBVIEW_WINDOW_CLOSE)` → with `exitProcessOnClose: true`, `app::exit()` →
`window::_close()`, which does `dispatch_sync` on the main queue while on the main thread. Neutralino's main of
2026-10-29 is unchanged. Quit (Cmd+Q) is not affected: `app.exit` from the page arrives on Neutralino's server thread.
**Fix (D506):** `exitProcessOnClose: false` in the three macOS configs; the shell page ends the app on `windowClose`
with `app.exit`, like Quit, and registers that listener first. Tests first: `tests/shell-page.test.ts` ("closing the
window"), and `tests/build-shell.test.ts` checks the flag in each config. **Not yet measured** on a Mac: the fix is
checked by the unit tests only; the acceptance is closing each of the three windows with the close button, before and
after a document is open, and the app ending without a crash report. Upstream: worth a Neutralino issue (run the block
directly when already on the main thread).

## Code review of 2026-11-15 at `7994b00`

Owner's request: duplication, separation of concerns, naming, convoluted solutions. Overview, order of work and open
questions: `notes/code-review-2026-11-15.md`. Evidence is **read** at `7994b00` unless it says **measured**.

### CODE-27 · The object methods are written once in the kernel and three times on the wire · P2 · fixed 2026-11-19
`claudia_core.objects` says an app "does not bring its own copy of place-an-object, take-it-away, stack-it, size-it"
(D177), and in the kernel that holds. One layer up it does not: `add_image`, `describe_object`, `move_object`,
`resize_object`, `rotate_object` and `remove_object` are written per app in `claudia_server/computes.py` (786–870),
`creates.py` (129–210) and partly `composes.py` (495–520). The bodies are the same; only the anchor
(`CellAnchor`, `SlideAnchor`, `BlockAnchor`) and the container check differ. Around them: `_rev(ctx)` three times
(computes 501, composes 137, creates 110); a fresh-id generator in `creates._fresh(prefix, taken)` (115), a copy of it
in `rendered.py` (115), and four single-prefix copies in `computes.py` (214–248); "execute, then answer the revision"
spelt out 25 times in `computes.py` where `creates.py` has `_done` (124). The apps also register methods two ways
(decorators in computes and composes, `_add_*_methods(table)` in creates).
**Recommendation:** one `claudia_server/object_methods.py` on the model of `search_methods.py`: an app supplies a
small adapter (anchor from the request's parameters, which container it is in) and the shared handlers are registered
once on its table. `fresh_id(prefix, taken)` and `done(ctx, command, base, **extra)` live there too. Test first: one
parametrised test that runs the six methods against all three apps.
**Fixed on the server (2026-11-15):** `claudia_server/object_methods.py` registers `images`, `add_image`,
`describe_object`, `move_object`, `resize_object`, `rotate_object` and `remove_object` once; each app gives a
`Placement` (`CELLS`, `ON_SLIDE`, `IN_TEXT`), which `add_rendering_methods` takes too. `wire.py` holds `fresh_id`,
`done` and `current_revision` (six, three and three copies before). Tests first: `tests/test_server_object_methods.py`
holds every app's wire words for these methods and runs one object through all of them in each app; it failed for
composes, which now has `add_image` and `describe_object` on the wire. **Still open:** composes' menu entries and
screens for them (Edit ▸ Image…, Format ▸ Describe…), to be agreed as mock-ups first; the web sessions' copies
(CODE-35).
**Re-checked 2026-11-20 at `f34365f`.** composes has Edit ▸ Image… (`02bfc03`, 2026-11-17, one import dialog for the
three apps) and Format ▸ Name & describe…, Ctrl+Alt+D (`467614e`, 2026-11-19, D1317).

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

### CODE-33 · `claudia-client` is a package no client uses · P3 · fixed 2026-11-16
"What every client of a Claudia server shares": `TlsPolicy`. Only its own tests import it. The Linux shell cannot
(`clients/linux/README.md`, point 3: it needs Python 3.14 and `claudia-core`) and has its own `trust.py` and
`x509.py`; the other clients are TypeScript. But `claudia_client/trust.py` imports only the standard library: the
`claudia-core` dependency in its `pyproject.toml` is unused, and it is exactly what keeps the shell from using it.
**Decision needed:** delete the package, or drop the dependency, target 3.12 and let the Linux shell use it instead of
its own copy.
**Fixed (2026-11-16, D700):** deleted. Each client trusts a server with its own platform's TLS; the Linux shell keeps
its `trust.py` and stays without dependencies.

### CODE-34 · Atomic writes are written seven times; five lack the Windows retry · P3 · fixed 2026-11-16
`state._replace` (`claudia_server/state.py` 65) and `journal._replace` (`claudia_container/journal.py` 171) retry
`os.replace` on Windows, where antivirus and indexing hold just-written files. The plain `os.replace` in
`claudia_fonts/starter.py` (107), `claudia_fonts/webfonts.py` (65), `claudia_server/hyphenation.py` (206) and
`claudia_typeset/cache.py` (64) runs in the same server, which the Windows client starts, so those writes can fail
the way the other two did. Separately, `starter.py` and `hyphenation.py` share `FetchError`, `read_lock`, `_download`,
`_write` and `fetch` nearly verbatim (pinned downloads checked against a lock file).
**Recommendation:** `write_atomically(path, data)` with the retry in one shared place (`claudia_core` or a small
utility module) used by all seven; one pinned-download helper for fonts and hyphenation patterns.
**Fixed (2026-11-16, D701):** a new package, `claudia-file-writer` (not `claudia_core`: the kernel does no I/O). Every
writer of the server uses it, the container's document file (an eighth copy) included; `trust.py` went with
`claudia-client` (D700). The retry runs in the Linux tests too (a fake `replace`). Two things the count missed: the
fetches run only when an operator asks, so the real Windows exposure was the web font cache and the typeset cache; and
a web font file being sent is held open on Windows longer than any retry, so it is written once (`write_once`),
finding it there being success. `starter.py` and `hyphenation.py` share `fetch_pinned`.

### CODE-35 · The web sessions repeat their write call 57 times and three shared methods · P3 · new, open
`(await this.attempt('<method>', { …, base: this.state.revision })) !== false` appears 24 times in `lib/session.ts`,
16 in `text-session.ts`, 15 in `slide-session.ts` and 2 in `base-session.ts`. `replacePalette` and `checkCss` exist
in all three sessions (identical in computes and creates). composes' session checks `denied()` and wraps writes in
`act()`; the other two do neither.
**Recommendation:** `protected write(method, params)` in `BaseSession` that adds `base` and answers a boolean; palette
and CSS checks moved into `BaseSession`; one write path for all three, or a comment saying why composes differs.

### CODE-36 · `localStorage` is guarded six times over · P3 · new, open
`safeStorage()` is defined in `lib/ai-mode.ts` (35), `server-bookmarks.ts` (21), `admin-session.ts` (37),
`show-prefs.ts` (25), `grid.ts` (27) and `theme.ts` (39); `OpenDialog.vue`, `TextWorkspace.vue`, `StyleSpec.vue`,
`locale.ts` and `mine.ts` have their own try/catch, and `remembered()` exists three times with different signatures (`OpenDialog.vue`, `TextWorkspace.vue`, `StyleSpec.vue`).
**Recommendation:** `lib/storage.ts` with `safeStorage()` and `remembered(key, allowed, fallback)`.

### CODE-37 · Two image dialogs that differ in one prop · P3 · new, open
`ImageImportDialog.vue` (creates) and `SheetImageImportDialog.vue` (computes) are the same 160 lines, CSS included;
they differ in the session type and in `frameFor` versus `anchorFor`. The first one's header comment still says
"Insert ▸ Image"; the menu entry is Edit ▸ Image… (`manifest.py` 1020).
**Recommendation:** one dialog with a `place(data) => Promise<string | null>` prop each app supplies.

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

### CODE-40 · An orphaned build file in the macOS creates app · P3 · fixed 2026-11-15
`clients/macos/apps/creates/inject/claudia-bridge.js` (16 KB) is an esbuild bundle of `src/menu.ts`, `src/page-bridge.ts`,
`src/file-dialog.ts` and `src/inject-entry.ts`; the last three no longer exist, and no config, script, test or source
names the file. composes and computes have no such folder. It is the leftover of the superseded D159 adapter.
**Recommendation:** delete it once a build of the creates bundle confirms nothing picks it up.
**Fixed (2026-11-15):** not carried over into `clients/neutralino/` (D660); the creates build and its tests pass without it.

### CODE-41 · Import cycles in computes are worked around with function-level imports · P3 · new, open
**Measured:** ruff's PLC0415 is off for the whole repository ("local imports break the kernel's import cycles on
purpose"); there are 44 such imports, 29 in `claudia_computes`. Two directions of knowledge cause most of them:
`CellRegion.transformed` (`region.py` 43) imports and switches on command classes, so every new structural command
means editing the region; `WorkbookModel` imports its own commands (`model.py` 488, 655) to build its first sheet and
to rename a sheet as commands.
**Recommendation:** let a command say how it moves a region (a method, or a table keyed by command kind) and move
command construction out of the model; then turn PLC0415 on per package with named exceptions.

### CODE-42 · Exports named a generic font family by a font Claudia does not show · P3 · fixed 2026-11-16
**Measured** (found while building E3.13 a and b): a third copy of the generic families,
`claudia_composes_io._style_look._GENERIC`, wrote a style whose font is `serif`, `sans-serif` or `monospace` into
docx and odt as Liberation Serif, Sans and Mono; `system-ui` was skipped for the next family and `ui-monospace` was
written as a font name. computes wrote the first family as it was, so `serif` or `system-ui` became a font name in xlsx
and ods. Claudia shows and prints those styles in Fraunces, Inter and JetBrains Mono (D905), so the exported file
looked different from what the person saw. Small in practice: only styles whose list starts with a generic family.
**Fixed (2026-11-16, branch `font-server-ui`):** the table moved into the kernel (`claudia_core.stand_ins`: generic
fonts, CSS names for a generic family, same-width stand-ins); both exporters call `file_font`; `claudia-fonts` and the
layout library's generated copy read the same table. Tests on the shared sample `test-documents/xlsx/stand-in-fonts`
(`generic_families`) for docx, odt, xlsx, ods and print (`implementation-notes/e3-13-font-stand-ins.md`).

### CODE-43 · docx and odt import ignored the file's fonts and reported no loss · P2 · fixed 2026-11-16
**Measured** (found while building E3.13 a and b, reported as bug 1): `docx_to_text` and `odt_to_text` read no font,
so every imported text showed in the app's own fonts, and `docx_import_losses` / `odt_import_losses` said nothing
about it. Exactly the case E3.13 is about: a Word file in Arial came in as Inter.
**Fixed (2026-11-16, branch `font-server-ui`):** both importers give Body text, Title, the headings and Quote the font
their style has in the file (docx: own or theme font along `basedOn` and the document defaults; odt: font face or
`fo:font-family` along the parents and the default style), as `css_family` makes it; the exporters write it back. New
in the libraries: `claudia_opc_io.ThemeFonts`, `claudia_odf_io.font_faces` and `font_of`. Tests on
`test-documents/docx/` and `odt/stand-in-fonts`.

### CODE-44 · pptx and odp import did not read fonts · P2 · fixed 2026-11-16
**Measured** (reported as bug 2): `pptx_to_slides` and `odp_to_slides` read no font, and a run or span naming one was
reported as `formatting`. A deck in Arial and Georgia came in as Inter.
**Fixed (2026-11-16, branch `font-server-ui`):** Body text takes the deck's body font (theme minor font; odp: default
style of drawn things); a box in another font gets a style of its own based on Body text, named by the font until
somebody names it. `slides_to_pptx`, `slides_to_odp` and `apply_edits_to_odp` write the fonts. A font is no loss;
words in two fonts in one box are `formatting`. Tests on `test-documents/pptx/` and `odp/stand-in-fonts`. **Left:**
placeholders of a pptx are not imported at all (reported separately).

### CODE-45 · pptx placeholders (titles, body text) are not imported at all · P2 · new, open
**Measured** (found while fixing CODE-44, reported to the owner as bug A, size 1): `pptx._classify` takes text boxes,
auto shapes and pictures only, so a placeholder — the title and the body text of nearly every slide made from a
layout — is left out of the model, and with it its words and its font. Most decks from PowerPoint come in nearly empty.
The stand-in-fonts sample uses a text box for its title for that reason. **Acceptance:** a deck made from the default
"Title and Content" layout imports with its title and body as objects (in their placeholder's place and size, the
title's words in the theme's heading font), round-trips through `apply_edits_to_pptx` keeping the placeholder, and
`pptx_import_losses` reports nothing for them. Touches the object ids, the losses and the export; its own patch.

### CODE-46 · The slides importers do not read text size and colour, so most boxes are a `look` loss · P2 · fixed 2026-11-17
**Measured** (reported as bug B, size 2): `pptx_to_slides` and `odp_to_slides` read the words and (since CODE-44) the
font of a box, not its size or colour, so a box with PowerPoint's 18 points or a coloured title comes in as Body text
and is reported as `look`. **Acceptance:** sizes and colours of the stand-in-fonts sample's boxes come in as the
styles' `font-size` and `color` (a provisional style per look, as for fonts) and are no loss.
**Re-checked 2026-11-20 at `f34365f`.** `_pptx_looks.read_look` reads `sz` and the run's `solidFill`, `_odp_looks` reads
`fo:font-size` and `fo:color`; the look book makes styles of them (D467). Placeholders are still not read (CODE-45).

### CODE-47 · Words of a docx with a font of their own are a `formatting` loss · P3 · new, open
**Measured** (reported as bug C, size 3): a run with its own `w:rFonts` (not through a style) keeps the paragraph
style's font and is reported as `formatting`, since the text model has no direct formatting (D306). Belongs with the
way direct formatting comes in (D379 for computes: provisional styles); until then the loss report is right.

### CODE-48 · After naming the first administrator, the server settings stayed on the setup form · P3 · fixed 2026-11-17
**Measured** (found while building Server settings ▸ Fonts, reported to the owner as bug D, size 3): `AdminApp.vue`
chose the setup form from the status read when the page loaded (`administrator: null`) and never read it again, so
after "Create administrator" signed the new administrator in, the form stayed until the page was reloaded. Every new
server is set up this way.
**Fixed (2026-11-17, branch `font-server-ui`):** `adminScreen` (`web/app/lib/admin-api.ts`) chooses the screen, and
somebody signed in always sees the settings; once somebody is signed in, signing out asks who signs in instead of
offering the setup again. Tests in `tests/admin-api.test.ts`; `e2e/admin-fonts.cjs` names the first administrator on
a new server and goes on without a reload.

### CODE-49 · Add fonts… stayed blocked for 30 minutes after too many files were chosen · P2 · fixed 2026-11-17
**Measured** (by the owner on 2026-11-17, reported as bug E, size 2): the dialog sent the chosen files one by one,
so choosing too many filled the server's room for waiting files (64 files or 128 MB) before the refusal came. Nothing
let go of them: not "Start again", not Cancel, not closing the dialog. Every later try, even with one font, was
refused with "too many fonts are waiting to be added" until they ran out after 30 minutes or the server restarted.
**Fixed (2026-11-17, branch `font-server-ui`):** the page sends the limits (`limits`) and the dialog says them before
anything is sent; a failed upload, "Start again", Cancel and closing let go of the held files
(`DELETE /api/admin/fonts/files`); the server holds files per administrator, so one person's leftovers never block
another; the refusal names the limits and what to do. Tests in `test_server_admin_fonts.py` and
`tests/admin-fonts.test.ts`; `e2e/admin-fonts.cjs` chooses 65 files (refused before sending) and starts again (let go).

### CODE-50 · LaTeX formulas ignored fonts added while the server ran · P2 · fixed 2026-11-17
**Measured** (by the owner on 2026-11-17, then reproduced): after adding the Latin Modern fonts under Server settings ▸
Fonts, a LaTeX container still said the font was missing. `FontService.reload()` makes a new `Catalogue`, but the
LaTeX plugin (and the typesetter it builds, with its fontconfig) kept the one it was made with at server start. The
fonts page listed Latin Modern Roman; the container's own list did not have it. The Fonts page itself said LaTeX
would use added fonts "after the server restarts".
**Fixed (2026-11-17, branch `font-server-ui`):** `builtin_registry` and `LatexPlugin` take a function that gives the
catalogue; the plugin asks on every job and makes a new typesetter when the catalogue changed. The server passes
`lambda: fonts.catalogue`; the page no longer mentions a restart. claudia-render 0.2.0 (API change, 0.x). Tests:
`test_render_latex_fonts.py` (no TeX needed) and `test_server_fonts_latex.py` (adds Latin Modern through the page's own
`add_collection`, reloads, and sets a formula with the real XeLaTeX).
**Which files LaTeX needs:** a font of the family "Latin Modern Roman" (the family name is what counts; every design
size, `lmroman5` to `lmroman12`, has it; at least `lmroman10-regular.otf`, for bold and italic also
`lmroman10-bold.otf`, `lmroman10-italic.otf`, `lmroman10-bolditalic.otf`) and the math font `latinmodern-math.otf`
(in TeX Live under `fonts/opentype/public/lm-math/`). `lmsans`, `lmmono` and `lmromancaps` are other families.

### CODE-51 · A container whose picture was never made stayed on "Drawing…" for ever · P2 · fixed 2026-11-17
**Measured** (by the owner on 2026-11-17, reproduced in `test_server_rendering_jobs.py`): a picture is made only when a
container's text changes (`Hub._schedule_render`). A container that never got one (the tool failed, a font was
missing, the server stopped first) was saved without it, and opening the document again drew nothing. The client says
"Drawing…" for a container with no picture and no outcome, and the outcome (`render_result`) was an event only: a
window that joined later never heard that the try had failed.
**Fixed (2026-11-17, branch `font-server-ui`):** a loaded document draws each container that has text and no picture
(`HostedDocument.render_unfinished`, called when the hub opens it); the last outcome of each container is kept and
sent with `renderings` (`outcome`, additive), so a window that joins later says "could not draw it" with the reason.
A new text clears the old outcome. A container with a picture is left alone. Tests: `test_server_rendering_jobs.py`
(six), `tests/rendering.test.ts`.

### CODE-52 · A TeX error was cut at 79 characters · P3 · fixed 2026-11-17
**Measured** (reproduced with the real XeLaTeX): TeX cuts a line of its log at 79 characters and goes on in the next
line; `parse_log` took the first line only, so a container said "Package fontspec Error: The font \"Latin Modern Roman\"
cannot be f" or just "Fatal Package", which is why the owner could not tell that the `xetex` program was set where
`xelatex` belongs ("Fatal Package fontspec Error: The fontspec package requires either XeTeX or LuaTeX").
**Fixed (2026-11-17, branch `font-server-ui`):** the engine runs with `max_print_line` set high and `parse_log` joins the
lines a message goes on in (the lines that begin with the package's name in brackets, and the line after one cut at the
width). Tests: `test_typeset_source.py` (real samples), `test_typeset_engine.py`, `test_typeset_real.py`.

### CODE-53 · The failure text of a rendered container is clipped in a small frame · P3 · open
**Read** (`RenderedFace.vue`, `.state` has `overflow: hidden`; the frame is as big as the picture was): a long message,
and the lines of the diagnostics under it, are cut off with no way to read the rest in the container. Recommendation:
the face shows the first line and the full message is in a tooltip and in the object's description, or in a popover
opened with Enter; the message stays an alert for screen readers in full. Acceptance: a test that a 300-character message
is reachable in full from the face (text in the DOM, not hidden from assistive technology).

### CODE-54 · A finished picture is kept without the fonts in its key · P3 · open
**Read** (`RenderService.render`): the key of the cache of pictures has the source, settings and the tools, not the font
catalogue. The typesetter's own cache has the catalogue digest, but the service's cache answers first. After a font of
the same family and style is replaced (or added in front of a stand-in), a formula drawn earlier is still shown as it
was drawn until the cache is cleared. Recommendation: a plugin may give a `cache_token()` (the LaTeX plugin gives the
catalogue digest) that goes into the key. Acceptance: draw, replace a font, draw again: a new picture.


### CODE-55 · A tool path changed in Server settings was used only after a restart · P2 · fixed 2026-11-17

Found: an administrator set `xetex` instead of `xelatex`, corrected it, and the container still failed until the
server was restarted. Cause: `cli._renderings` copied the typeset paths into the `ToolRegistry` once at start, and the
registry also kept every tool it had found. Fix: the registry takes a function for its table, asks it on every use and
forgets what it found when the table changed; the server passes the live settings. Test: a tool found under the old
setting is not used after the setting changes; the server's table follows `settings.typeset`. Open: `rsvg_convert`
(`render.tools`, not editable in Server settings) is still read at start; Server settings has no check that the
program is a LaTeX engine (`xetex` is not one).
## Reported 2026-11-17, found while building the text structure (step D)

### CODE-56 · A new sheet can get the id of a removed sheet · P3 · new, open
**Read** at `5dbccde9`: `_fresh_sheet_id` in `claudia_server/computes.py` (used by `add_sheet` and `define_pivot` with
a new sheet) starts counting at the number of sheets, so an id that a removed sheet had is free again. Sheets `s1`,
`s2`, `s3`; Ann removes `s3`; Ben adds a sheet, which is `s3`; Ann's undo of her removal brings back a second `s3`
(or is refused), and history entries that name the old `s3` now mean Ben's sheet. Objects had the same flaw and were
fixed on `main` with `wire.fresh_id` (bug 5 of the text-structure work, 2026-11-16).
**Acceptance (the test to write first):** add three sheets, remove the last, add one: the new id is not the removed
one, and undoing the removal brings the removed sheet back beside the new one.
**Fix:** take sheet ids from `wire.fresh_id` (or a counter in the workbook that never goes down), as objects do.

### CODE-57 · Undoing typing after an undone delete that cut into it removes the wrong characters · P2 · fixed 2026-11-17
**Found** while building step G (typing in text boxes); older than it, in composes and creates alike. "a note"; Ben
types " short" after the "a"; he deletes "a " (which takes the start of his typing with it), undoes that, then undoes
his typing: "a sote". `Document._step` followed the undo through every later step, the delete and its own undo too;
a delete loses where inside the cut words a span began, so putting them back moved the span to the wrong place.
**Acceptance:** `test_undoing_typing_after_an_undone_delete_that_cut_into_it_takes_out_exactly_the_typing` (creates
and composes): the second undo gives "a note", and a redo gives "a short note" again.
**Fix:** a step undone (or redone) by the very next entry of the log is left out with that entry when an older step is
followed forward (`document._standing`): the two together changed nothing.

## Website

### WEB-01 · The website describes features the product does not have · P1 · needs decision
From the first round, and worth re-checking now that more is true: encryption, formulas and a Linux client now exist,
so several of the claims have caught up. Import and export of Word, Excel, PowerPoint and OpenDocument files still do
not exist in any form (no code under `packages/*/src` touches those formats), and "run in a European cloud" has no
images or deployment behind it.
**Decision needed.** Either mark each item *planned*, or soften the wording until it is true. The honest "what works
today" block proposed in the first round would now be a strong one: live co-editing, history, presence, per-document
passwords and encryption at rest, recovery keys, formulas, styles, three apps, a Linux client.

### WEB-02 · Download buttons are `#` placeholders · P3 · open

---

## Round of 2026-11-17 (stabilisation, `main` at `f150f0d`)

### PROC-24 · `main` was red after the merge of all branches · P1 · fixed 2026-11-17
Two tests failed: `test_backlog` (story id E3.13 used by the font story and by the redaction screens) and
`test_decision_log` (D730–D735 numbered twice: Windows packaging and another branch). **Fix:** the redaction screens are
E3.14, the Windows decisions are D740–D745 in every file that names them (workflow, packaging, clients, tests, tasks).
**Process.** A merge of several branches needs `scripts/check_debt.py --fast` before it is pushed; number clashes are
the typical result of parallel branches, so `ranges.md` should hand each branch its own range up front.

### PROC-25 · The demo deployment was not gated on CI · P2 · fixed 2026-11-17
`deploy-demo.yml` ran on the image workflow, so a red `main` still went live. **Fix:** it now runs on `workflow_run` of
`CI` (success only) and waits for the image with a retry. `tests/test_ci_workflow.py` pins both.

### PROC-26 · No dependabot · P3 · fixed 2026-11-17
`.github/dependabot.yml` watches uv, npm (web, layout, neutralino), the Dockerfile and the actions; a test fails when a
lockfile is added that is not watched.

### PROC-27 · Supply chain in CI · P2 · fixed 2026-11-17 (D762)
Actions were referenced by tag; the image workflow tagged `latest` before CI was green; no CodeQL, no `pip-audit` (SEC-08).
**Fixed.** All 44 `uses:` of other people's actions are `@<sha> # v<version>` (the latest release of the major version
they followed); `promote-image.yml` points `:latest` and `:main` at the commit's image after a green CI (`docker.yml` now
pushes `sha-…` and the release tags only); `codeql.yml` (Python, TypeScript); `pip-audit` job in `ci.yml`.
Tests: `tests/test_ci_workflow.py` (pins, tags, promotion, CodeQL, pip-audit).
**Not seen:** the first runs. Needs on GitHub: Code scanning enabled, CodeQL's "default setup" off. Open from here:
`signpath/github-action-submit-signing-request` pinned to v1.3 (the major it used); the workflows could move to the
newer majors (checkout 7, setup-node 7, setup-uv 9, …) through dependabot's pull requests, one grouped PR a week.

### CODE-58 · The creates exporters drop style properties without saying so · P2 · fixed 2026-11-17 (D760)
`StyleDef.css` of a creates style may hold `border-left`, `padding-left`, `line-height`, `letter-spacing`; the pptx and
odp exporters write size, colour, alignment, family, weight and background only (`_styling.py`), yet `_unwritten.py`
lists `styles` as written, so `pptx_export_losses` and `odp_export_losses` both return `()` for a model with those
properties (probe 2026-11-17). The composes exporters do write border, padding and spacing, so the two apps differ.
**Fix.** Either map the properties (pptx `a:lnSpc`, `a:ln`, insets `lIns`; odp `fo:` equivalents) or make `styles` a
partial facet and report each unwritten property under a loss code. **Acceptance.** A bordered, padded style exports
with a loss entry naming the property, or is written and read back unchanged.
**Fixed (D760): reported.** `style-property` is a loss, with the property as detail and the number of objects as count,
judged against the built-in defaults (`_styling.unwritten_properties`, tests `test_unwritten_styles.py`). Not done:
writing the properties (the list of losses is what is left to map).

### CODE-60 · Drift: facts written twice and drawn in one place only · P2 · fixed 2026-11-17 (D761)
(1) The web has its own list of built-in style ids and `'body-text'` literals while `claudia_composes.model.BUILTIN_STYLES`
and the creates styles are the source; (2) `layout/src/apps/objects.ts` `VisualObject.kind` has no `rendered`, which the
server allows (CODE-24); (3) `TextEditor.vue` draws list leader dots in CSS while the display list and the exporters
differ. **Fix.** The server sends flags with the style list (built-in, heading level, default) and the web reads them;
the kind set comes from the generated layout fixtures (`scripts/generate_layout_fixtures.py`) like the headings
(`test_one_source_of_headings.py`). **Acceptance.** A test that fails when a kind or built-in style id exists in only one place.
**Fixed (D761).** (1) `scripts/generate_style_ids.py` writes `layout/src/styles.generated.ts` (each app's default style,
the style of a shape's words); layout and web import it; `tests/test_style_ids_generated.py` refuses the literals.
(2) The layout has `ObjectKind` (= `claudia_core.OBJECT_KINDS`, `tests/test_object_kinds_agree.py`) and prints a
`rendered` object as its picture, or leaves it out; the web's two copies of that rule are gone, and the web types import
`ObjectKind`. (3) `layout/src/text/leader.ts` has the gap, step and size of the dots once; the printed pages use it and
the screen draws the leader with `leaderCss` (the editor's was 0.4 em and a dotted border, the agenda's 0.3 em: both
now as the pages draw them). **Left:** the Format menu names three called-out styles (CODE-63); the exporters' name
tables stay as they are (they map to other programs' names).

### CODE-61 · Stale backlog statuses · P3 · fixed
E9.30, E10.21 and probably E9.31 say open where code and tests exist. **Fix.** Check each against the tests it names and
set its status; `tests/test_backlog.py` could require a test path in every story marked done.
**Re-checked 2026-11-20 at `f34365f`.** E9.30 and E9.31 say `done`, E10.21 `in-progress`. The test that a story marked
done names its tests is not built.

### CODE-63 · The Format ▸ Styles menu lists composes' contents styles as "custom" · P3 · new, open (read)
`TextWorkspace.vue` groups the styles of a text: headings, Body text, three called-out blocks, then `customStyles()`,
which is every paragraph style that is neither of those nor a heading. `contents-title` and `contents-1`…`contents-9`
are built-ins of composes (the look of a table of contents' lines) and are paragraph styles by kind, so they land in
the trailing "custom" group of every document. Found while replacing the web's own list of built-in ids (CODE-60).
**Fix.** Decide whether a person applies them to a paragraph at all (the contents entries take them by themselves). If
not, send a flag with each style view (`"for": "entries"`) and leave them out; this is also the way to remove the
three hand-written ids. **Acceptance.** A new text's Format ▸ Styles menu has no `Contents 1`.

### CODE-64 · The browser editor does not draw the text wrap · P2 · fixed 2026-11-18
The engine lays out the lines round the objects for print and View ▸ Page (D1062). The flowing editor view
(`TextEditor.vue`, contenteditable) cannot: the browser lays out its lines. A new picture, shape or box defaults to
*above and below* (D1061), so in the flowing view it overlaps words that print beside or around it.
**Fix.** Stage 2 of D1062: either put the editor on the engine's rows in a mode of its own, or give the browser the
same exclusions with a CSS `shape-outside` float per object. **Until then** decide whether new objects default to
*over* in the flowing view. **Acceptance.** An object with *around* shows the same line breaks on screen as in the print preview.
**Fixed** with one float per object (D1068), checked in a real Chrome (`npm run e2e:composes-wrap`). What the browser's floats cannot do is in D1068.

### CODE-65 · `dx`/`dy` of an object is not exported · P2 · fixed 2026-11-18
`composes_io` writes the anchor character and the wrap, not the offset an object has been moved by. **Fix.** DOCX
`wp:posOffset`, ODF `svg:x`/`svg:y` with `text:anchor-type="char"`; import the same. **Acceptance.** Round trip keeps the offset within one pixel.
**Fixed** (D1067): round trips for text boxes and pictures in every wrap mode, rotated pictures and a kept file's move; the positions were checked by rendering with LibreOffice.

### CODE-62 · A window that revives the shared server while the old one still holds the port starts it on a random port · P3 · new, open
**Measured** (found while fixing the `deb.yml` job on 2026-11-17, reported to the owner as a size 3 bug): D445 says
every app of the suite talks to one shared local server on the same port. When the server is gone, a shell window
revives it (`_keep_presence` in `clients/linux/src/claudia_shell_gtk/desktop_server.py`). If the old server process
is still shutting down and holds the port, `free_port` chooses a random one, so the revived server lives on a port
nobody has remembered and `desktop-server.json` and `CLAUDIA_SERVER_PORT` no longer agree with it. The CI job showed
it: the window was ended after the server, revived it on a random port, and the new server then found the folder lock
of the old one ("another Claudia server uses …/documents"). The Neutralino twin, `clients/neutralino/src/desktop-server.ts`,
is built the same way and is likely affected (**read**, not run).
**Acceptance:** a test in which the first server still holds the port while a window revives it: the revived server
waits for the port (a bounded time) and starts on the same one; only when the port stays taken does it say so, instead
of silently using another.
**Worked around** in `deb.yml` (the window is ended first, then the server is waited for); the cause is not fixed.

### SEC-19 · Imports have no memory cap · P2 · open
Imports run on `hub.workers`; `check_package` refuses bombs by declared size, but a 512 MiB package may still build a
model several times that size, in the server's own address space. **Fix.** Run import in a worker process with a
resource limit (`RLIMIT_AS`), or lower the defaults for a public demo. **Acceptance.** A hostile 500 MiB part of
many small nodes is refused with a sentence and the server stays up.
**Also:** SEC-11 (no back-off on failed logins) is P2, not P3, for as long as the demo is public.

### UX-44 · Blinking dots ignored reduced motion · P3 · fixed 2026-11-17
`SidePanel.vue` `.dots i` now stops animating under `prefers-reduced-motion: reduce` (WCAG 2.3.3).

---

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

### CODE-66 · A picture added to an imported workbook is not written into it · P3 · new, open
`apply_edits_to_xlsx` / `apply_edits_to_ods` change only the cells, looks, names, widths and charts of the original file's XML;
a picture added in computes after an import is reported (`object`) and not in the file (a fresh export has it, D1233).
**Fix.** The patch adds an `xdr:pic` and its media part to the sheet's drawing (`Drawings.add_picture` is there for it) and a
`draw:frame` and its `Pictures/` part to the sheet's `table:shapes`; moving, turning or describing a picture changes its frame
or anchor; removing one takes it and its part out. **Acceptance.** Import a workbook, add, move, turn and remove a picture,
export: the file has what the model has and `xlsx_unwritten_changes` is empty (`test_pictures.py`, a patch case for each).
Found while building D1233.

### CODE-67 · The pictures of an XLSX or ODS are not read into the model · P3 · new, open
A picture in an imported workbook stays in the file untouched and is counted as `picture` on import, but computes does not
show or select it. **Fix.** Read `xdr:pic` / `draw:image` frames (size from the anchor and the widths and heights the sheet
has, as for charts; `rot`, `descr`, `name`) as image objects with the asset decoded from the media part, as `file_charts`
does for charts. **Acceptance.** An imported picture is on the sheet, has the file's size and turn, and writes back to the
same place (`test_pictures.py`, a round trip for each format). Found while building D1233.

### Second list of 2026-11-19: every open point of `object-interaction`

Entered at the owner's request, from the decision log, the contract note and the delivery reports of the branch.
Evidence is **read** unless it says otherwise; none of these was run in a browser (see PROC-28).

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

### CODE-69 · A shape's text is a plain string · P3 · new, open
The shared object layer keeps a shape's text as `str` (`implementation-notes-shared-object-layer.md`, "Not done"). Promoting
it to composes' `Block` would give it styles and authorship, but needs an overflow policy per host (a paragraph in a fixed
box cannot push anything down). **Acceptance.** A shape's paragraph has a style and a run with an author in all three apps;
an overflowing box shows its overflow by the host's rule (clip or grow), tested per host.

### CODE-70 · The patch of a kept file does not add pivot tables · P3 · new, open
Same cause and same shape as CODE-66: `apply_edits_to_xlsx` / `_ods` change what the file already has. A pivot table
defined in computes after an import is reported and not written. **Acceptance.** Import a workbook, define a pivot, export:
the file has it, or `xlsx_unwritten_changes` names it and the test says so.

### CODE-71 · The context menu types its key hints by hand · P3 · new, open (read)
`web/app/lib/object-menu.ts` writes "Enter", "Ctrl+X", "Ctrl+C" and "Del" as strings where the other entries use `hintOf`; the manifest owns the keys
(`keys.generated.ts`). The two can drift, as the missing Delete entry shows (UX-47). **Fix.** Hints come from the generated
table by action id. **Acceptance.** A unit test fails when a hint differs from the manifest's key.

### PROC-28 · `objects.cjs` has never run · P2 · fixed 2026-11-20
D1231 wrote `web/e2e/objects.cjs` (and its guard `tests/test_object_kinds_agree.py`, which runs) and wired it into
`npm run e2e:objects` and CI; the sandbox it was written in has no browser, so no step of it has run, and the table step
and the Rotate steps of patches 9–10 are as untested. **Acceptance.** `npm run e2e:objects` is green on a machine with a
browser; every red step is a bug of this list or a new one, entered here.
**Re-checked 2026-11-20 at `f34365f`.** `objects.cjs` ran first on 2026-11-20 (branch `fix-table-exit-object-sizes`):
one stale step of its own (`rotateOff`) was fixed there; steps 1–4 pass in computes and creates; what still fails is the
app's: UX-56 (creates), UX-57 (computes), UX-58 (composes).

### PROC-29 · The holder's outline and name tag are not asserted · P3 · new, open
Step 8 of the battery (D1231: a second window sees the holder's outline and name tag while the object is selected, no drag
live, only the result, D1223) asserts only that the object, its removal and its return arrive. **Acceptance.** Two pages,
page 1 selects an object: page 2 shows an outline with page 1's colour and name tag, and page 2's move is refused or waits;
page 1 deselects and the tag goes. For every kind and every app.

### PROC-30 · The desktop clients were not run for this branch · P2 · new, open
Definition of done: all desktop clients work with the latest server and do not diverge from the web. For `object-interaction`
the Neutralino menus (`menu.composes.json`, `menu.computes.json`) were regenerated and the Linux manifest tests
pass; the Neutralino tests, the Windows and macOS clients and the GTK client's windows were not run. **Acceptance.**
The client tests of the three desktops pass, and a hand check on each of Format ▸ Rotate, Tools ▸ table commands and
Edit text in composes and computes is recorded in the implementation note.

### PROC-31 · `po/claudia.pot` goes stale at every merge of `main` · P3 · new, open (measured)
Merged onto `main` at `85109b8`, `extract_i18n.py` rewrote 43 lines of `po/claudia.pot`, **all `#:` source references**, no
msgid (measured). The i18n check of `check_debt.py` fails on that, so every merge needs a regeneration commit. **Fix.** Write
the catalogue without locations (`--no-location`) or let the check compare msgids only. **Acceptance.** Merging a branch
that moves a line of a translated file leaves the check green.

### PROC-32 · `claudia-menus.xlsx` is not in the repo · P3 · fixed 2026-11-19
The project says behaviours and keys are kept in `claudiaoffice-log/notes/claudia-menus.xlsx`; the file is not there (the
versions the owner sent in chat were not committed). What the branch changed is in the generated `keyboard-shortcuts.md`
only. Still to enter, from `notes/object-interaction-contract.md` ("For the workbook"): the table rows of the context menu
(D1224), "not for a chart or a table" on *Rotate by…*, the wrap entry (D1225), Format ▸ Rotate in composes and
computes, Delete (UX-47), the table commands in Tools (D1229). **Acceptance.** The workbook is in the repo and a test
compares its key column with the manifest.
**Re-checked 2026-11-20 at `f34365f`.** `claudiaoffice-log/notes/claudia-menus.xlsx` was added in `496b3db` (2026-11-19)
and has been kept up to date by every round since (the keys of D1330–D1334 and D1350–D1352 included). The test that
compares its key column with the manifest is not built.

### PROC-33 · Patches 9–11 failed the lint gate · P3 · fixed 2026-11-19
The last step of the series, the gate on the merged tree, found `ruff` errors (lines over 120 characters in `manifest.py`,
`clients/linux/tests/test_manifest.py` and `tests/test_object_kinds_agree.py`) that earlier steps had not run it
for. Fixed in patch 12. **Lesson, kept as the rule:** `scripts/check_debt.py` runs on the final tree of every series, not per patch.

---

## Round of 2026-11-19 (E2 second round, branch `e2-document-sec`)

### SEC-20 · Behind a proxy every client had the proxy's address · P2 · fixed 2026-11-19
**Evidence (read, then tested).** `Gateway.serve`, the lookup throttle and the upload desk took `client.host` from the socket.
With `--behind-proxy` that is the proxy. **Fix.** D1275: the `X-Forwarded-For` entry the nearest trusted proxy appended
(`--proxy-hops`, default 1). Tests: `test_server_client_address.py`, `test_server_cli.py`, `test_server_uid.py`.
**Not run:** a real proxy in front of a real server.

### SEC-21 · Password-confirming methods hash on the event loop · P2 · fixed 2026-11-19 on branch `e2-document-sec`
**Fixed (D1277).** Hashed in a worker thread behind the cap before the request is handled (`Method.hashes`, `Gateway.prepare`, the one-shot cache in `claudia_container.crypto`). `test_server_password_methods.py` failed first (the other window waited 0.19–0.42 s) and passes (under 50 ms, at most 2 hashing at once).

**Evidence (read).** `Connection.handle` is synchronous and runs in the loop; `SealedDocuments.set_details`,
`delete_document`, `leave`, `change_password`, the owner transfer and the new `sealed_copy` call `unlock` (one Argon2id run)
inside it. Logins are different: `Gateway._hello` runs `verify` in a thread behind the hashing cap (SEC-03). Today a run takes
0.1 to 0.4 s, at the 0.75 s of D1267 every one of these calls stops every connection of the server for that long, and a
person with a password can do it in a loop.
**Fix (proposal).** Make the handlers that take a password asynchronous, or move their hashing to the same thread pool and
cap as the login; with D1266's back-off for wrong passwords. Acceptance: while one of them runs, another connection's
`ping` is answered within 50 ms.

### CODE-72 · `KdfParams`' docstring was wrong · P3 · fixed 2026-11-19
Words only; D1267 says what is true.

### DOC-04 · The versioning page named protocol version 1 · P3 · fixed 2026-11-19
`tests/test_docs_versioning.py` fails when the page and `PROTOCOL_VERSION` differ.

### PROC-34 · The backlog branch broke the story/epic check · P3 · fixed 2026-11-19
The Obsidian project-manager plugin renamed the file after a title change (`e0.3-shells--gtk-with-webkitgtk-6.0-and-neutralino.md`).
The epic names `e0.3-shells-gtk-with-webkitgtk-6-0`; the file name is restored. It will happen again whenever a story title
is edited in Obsidian: `tests/test_backlog.py` is what finds it.

### CODE-73 · File ▸ Download did not write the sealed file · P2 · fixed 2026-11-19
D110 (current since 2026-11-02) and the workbook say Download is the sealed `.claudia` file; the code wrote the
unencrypted content JSON. Built as E2.12. The unencrypted export is now missing from the menus until E2.9 (owner accepted).

### PROC-35 · The e2e tests fail together and pass alone · P3 · fixed 2026-11-19 on branch `e2-document-sec`
**Fixed.** The spec runner's `browser` fixture was session-scoped, so its Playwright kept an event loop open for the rest of the run; it is module-scoped now. `uv run pytest tests/e2e` passes in one run (30 passed, 89 skipped, 2 xfailed). It was not compared with `main`; the cause was in this branch's runner or the one on `main`, which is the same file.

**Evidence.** `CLAUDIA_CHROMIUM=/usr/bin/google-chrome uv run pytest tests/e2e` (one process): `test_greeting.py` (2 tests) and
`test_computes_grid.py` fail with "It looks like you are using Playwright Sync API inside the asyncio loop"; run one file at
a time, all pass (greeting 2, grid 1, names 7). The new `tests/e2e/specs` run on their own (3 passed, 3 skipped).
**Likely cause (read).** `test_documents_between_servers.py` runs first and leaves a running loop. **Acceptance:** the
whole directory passes in one run, as CI runs it (`uv run pytest tests/e2e`). Check on `main` first: it may not be new.

## Verified positives (so nobody "fixes" them)

- The Python gate is genuinely green at `54d1245` on Python 3.14.6: ruff, mypy, vulture, **≈1,321 tests** (8 skipped,
  the Windows-only sandbox ones), Sphinx with warnings as errors, both performance guard suites, and the Linux client's
  own mypy and tests. Web: **195 vitest tests** in 14 files, `vue-tsc` clean.
- The container's cryptography is conservative and correct in shape: Argon2id with bounded parameters read from an
  untrusted file, HKDF with distinct labels per purpose, AES-256-GCM with a fresh random nonce and additional
  authenticated data naming document, domain and position, and a hash chain plus head record that detects a changed,
  swapped, moved or truncated block. Known-answer tests come from RFC 5869, RFC 9106 and the GCM vectors.
- The container reader defends against hostile files: entry count, entry size, total size, compression ratio, name
  pattern, no absolute paths or `..`, never extracting to disk.
- The typesetting sandbox is defended in depth and the defences are *mutation-tested*: weakening `-no-shell-escape`,
  `shell_escape`, `openin_any` or `openout_any` makes six hostile tests fail. 15 hostile-input tests run against the
  real engine.
- The formula engine is incremental and well-indexed: a dependency index with ranges filed by 256-row blocks per
  column, depth-first ordering with an explicit stack (so a 20k-deep chain is fine), cycle detection to `#CIRC!`, and
  `math.fsum` so sparse iteration order cannot change a sum.
- `PEP 758` syntax (`except A, B:`) is used deliberately and is valid on the project's Python 3.14; any tool that
  parses the tree needs 3.14.
- Credentials travel in the first WebSocket frame, never in a URL; the name `ai` is protected Unicode-aware; message
  size, text length, region count and `set_cells` size are limited; slow clients are dropped rather than buffered.

## Not reviewed (and why), round of 2026-11-13
Firefox (no Firefox here; every browser script ran in Chromium 153 only), the Windows and macOS clients on their own
systems (their window scripts ran with Neutralino faked), a screen reader, a real language model, the live demo, the
Docker image (no Docker daemon here: the Dockerfile was read, not built), the print output on paper or in Acrobat.

## Not reviewed (and why), round of 2026-11-12

A real language model (no model could be downloaded here; `./start.sh --ai` was run up to loading a stand-in folder,
which OpenVINO GenAI 2026.4 then refused as expected); Windows and macOS clients (nothing runs them here; the Windows
client is reviewed by reading only); the live demo at demo.claudia-office.de (not reachable from here, so SEC-12 there
is likely, not seen); screen readers; Firefox (the browser scripts ran in Chrome for Testing 153).

## Not reviewed (and why), round of 2026-11-05

The website (out of scope this round); the Neutralino shell (does not exist); a real language model (no model could be
downloaded); Windows and macOS (nothing was run there, and the Windows sandbox layer has still never executed); the
browser e2e scenarios (not run here); screen-reader behaviour (UX-01/02/03 are measured by reading and by script, not
by listening); the history panel's contrast on its dark background; ODF and OOXML (no code exists).

## Method, this round

Cloned `main` at `54d1245`, synced the environment with `uv sync --locked` (Python 3.14.6), ran the full test suite,
ran `scripts/check_debt.py`, installed the web packages and ran vitest and `vue-tsc`, and ran `ruff format --check`.
Read the server's gateway, hub, protocol, computes and composes method tables, the assistant and AI agent, the
container's crypto, container and journal, the calculation engine, the web menu, modal, grid and token files, the
Linux client's notes and manifest, the CI workflow and the quality gate. Wrote and ran three probes: a scaling
benchmark for the grid window and the sheet extent, a WCAG contrast calculation over the real tokens, and an
inspection of the AI's authorisation path. Cross-checked every claim in the implementation notes that asserted a file
or feature exists.

### SEC-22 · A viewer still receives who wrote which stretch · P2 · new, open (needs a decision)
**Evidence (read, `e2-document-sec`).** The authorship (`runs`) of every block is part of the content state: the `blocks`
method, the `text` events, the snapshot and so the viewer's own sealed file (content key) all carry it. D1261 says the
viewer's "show who wrote what" should have no data behind it. **Options.** (a) Mask `runs` for a viewer live and in her
file (a viewer's snapshot would be written without them: a second snapshot); (b) accept the authorship as content and say
so in D1261. **Proposal:** (b) until the owner says otherwise, because masking in the snapshot means the content is stored
twice. Not built either way.

### PROC-36 · A global `ruff` is not the project's · P3 · fixed 2026-11-19
`ruff 0.16.9` outside the project rewrote `except (A, B):` into `except A, B:` in five files and reformatted six others
that were not touched. `pyproject.toml` pins `ruff>=0.6,<0.15` for this reason. Use `uv run ruff`. **Fixed:** rule 5 of
`CONTRIBUTING.md` says so.

### UX-54 · The server settings pages have no keyboard shortcut · P3 · new, open
The pages of Server settings (AI model, Typesetting, Fonts, Security, Access & documents) are buttons in a sidebar with no
shortcut, and the menu workbook does not list them. The project asks for a shortcut for every menu entry; these are
navigation, not menu entries, so the owner may want to decide whether the rule covers them.

### PROC-37 · The history and chat of an export are not read back · P2 · new, open (needs a decision)
**Evidence (read, measured by the tests).** `write_export` puts `history.jsonl` and `chat.jsonl` in the zip for an owner and
`read_export` returns them, but `import_state` takes only `state`; the new document starts with one `core.Import` step. D1272
says the history comes in with its authors as plain text ("former people"). **Not built** because the history of an export
is the commands of another document, with revisions that mean nothing in the new one; what a person would want is the list of
who did what, not commands that can be undone. **Options.** (a) a read-only "History of the original" kept as one note in the
new document's history, text only, with the names as text; (b) the commands replayed with their authors as former people;
(c) log it and leave the import as content only. **Proposal:** (a) in slice C. The mock-up's sentence "The people named in its
history are not given access; their names stay in the history as former people" is **not** on the import dialog until this
is built; the dialog says "Nobody else is given access." and nothing about names.

### UX-55 · A window was not told of its own export · P2 · fixed 2026-11-19
Found by the first end-to-end run of `export-and-record.feature`: the scenario "Ann exports the document without protection"
failed because the History & Chat panel had no line. The server publishes `audit_recorded` to the other windows and not to
the sender; the unit test on the server only looked at another window. **Fixed:** `BaseSession.recorded` reads `audit_log`
again after the window's own export, print or PDF (owners and editors); `web/tests/session.test.ts` has the case.

### CODE-74 · `export_content` is a third kind of export nobody asked for · P3 · new, open
`export_content` (a JSON object with `format: "claudia-export 1"`) predates D1270 and is not called by any window. It is
recorded like every export (`leaves="export"`), under a format name the panel does not know. Either remove it or make it
answer with the zip; removing it changes the network API (a minor version while the major is 0).

### PROC-38 · A timing test needs a slower machine than the one it runs on · P3 · fixed 2026-11-21
`test_another_window_is_answered_quickly_while_a_password_is_hashed` first checks that hashing takes longer than 0.15 s, so that
"answered quickly" means something. On a fast machine, with the suite running in parallel, it measured 0.1499 s and failed;
alone it passes. Size 3: the test should set a cost of its own that is slow enough, not read the clock of the machine.

**Fixed 2026-11-21.** It was not only a fast machine under load: on the runners of CI the hash took 0.12 s every time, and the test failed on Linux, Windows and macOS in every run since it was written, which made the job "Python" red. The test now uses `claudia_container.kdf.calibrate` (the server's own measuring, D1267) with the old cost as its floor, aiming for twice the time it needs. The threshold of 0.15 s stays: what it says is the same.

### PROC-39 · The e2e server's output pipe was never read · P2 · fixed
`live.server()` started the server with `stdout=PIPE` and read it only when the server stopped early. A run with enough scenarios
(slice C added six) wrote more than the pipe holds, and the server's next `print` blocked inside the event loop: the next page load
timed out after 30 s. It showed as three failing `test_viewer` scenarios that pass alone. Found by bisecting which module had to
run before them; fixed by writing to a file. Size 2 (it would have hidden every later regression behind a timeout).

---

## Round of 2026-11-20 (tracker update, `main` at `f34365f`)

Every open item was re-checked against `main` at `f34365f` (after the merges of `e1-core`, `e2-document-sec`,
`fix-table-exit-object-sizes` and `fix-stale-tests-caret-drag`). Closed: SEC-08, SEC-11, SEC-17, CODE-13, CODE-27,
CODE-46, CODE-61, UX-37, PROC-28, PROC-32 (each with a line "Re-checked 2026-11-20" in its section). Still open after a
look at the code: SEC-12, PERF-02, PERF-10, CODE-19 (the scan moved to `claudia_file_writer/atomic.py`), CODE-20,
CODE-25, CODE-31, CODE-45, CODE-56, CODE-63, UX-21, UX-27, UX-45 to UX-47, UX-51, CODE-71, PROC-22, PROC-31. The rest
were not re-checked one by one: nothing on `main` names them as fixed. New items below.

### UX-56 · Enter in Rotate by… is taken by the slide in creates · P2 · fixed 2026-11-21
**Measured** (`web/e2e/objects.cjs`, 2026-11-20, while fixing the stale `rotateOff` step): with a text box selected,
Format ▸ Rotate by…, type an angle and press Enter: the key reaches the slide, which starts editing the box's words, and
the angle is not applied. The dialog should own its keys (Enter applies, Esc closes). Keyboard users cannot turn an
object by a given angle in creates. **Acceptance.** `objects.cjs` step "Rotate by…" in creates: Enter applies the angle,
one history entry, the box's words unchanged.

**Fixed 2026-11-21.** The popover sits inside the element that listens for keys, so every key typed in its field bubbled up: Enter began editing, and Backspace or Delete **deleted the selected object**; the arrow keys moved it. The slide and the cell grid (where Enter began a cell edit and so cancelled the form's submit) now leave a key that comes from a dialog inside them to the dialog. `objects.cjs` presses Backspace in the angle field and sees that the object stays (red without the fix), then Enter applies the angle. Both apps.

### UX-57 · The turn handle of a picture does not turn it in computes · P2 · fixed 2026-11-21
**Measured** (`objects.cjs` step 5, 2026-11-20): turning a picture by its turn handle times out waiting for the handle in
computes; steps 1–4 (select, drag, resize handles) pass. Cause not looked into: the handle may be missing for a picture
in a cell, or hidden under the grid. **Acceptance.** `objects.cjs` step 5 passes in computes.

**Fixed 2026-11-21.** The cause was one step earlier: the handles are drawn beside the picture, not inside it, so the `mousedown` that follows the press on a handle was not stopped as the picture's own is, and reached the grid's cell selection. That let go of the picture and selected the cells under the pointer (the screenshot showed D6:D7), so the next step found no turn handle. The wrapper of the handles stops the `mousedown` now.

### UX-58 · A press on a text box moves the caret below it in composes · P3 · fixed 2026-11-21
**Measured** (`objects.cjs` step 1, 2026-11-20): a press on a text box selects it, but the words of the paragraph under
it also take the press and move their caret. D1221: a press on an object is not heard by what lies below. **Acceptance.**
`objects.cjs` step 1 in composes: the caret's place before and after the press is the same.

**Fixed 2026-11-21.** The browser's own action on a press put the selection into the object's markup (the stem of its turn handle), out of every paragraph. A press on an object is now the object's (`preventDefault` on the pointer down), unless its words are being written in.

### UX-59 · Up between paragraphs may be undone by a re-render · P3 · new, open
**Measured once** (2026-11-20, `caret.feature` "Up from Second to First"): one run in four ended with the caret still in
the second paragraph. The scenario now waits for the caret to be placed before it presses a key, and has passed since.
The guess, not confirmed: a paragraph saved a moment before re-renders and puts back the caret the browser had just
moved. **Acceptance.** The scenario without its wait passes 20 runs in a row; or the race is shown and fixed in
`TextEditor.vue`.

### UX-60 · "Moved an object" for a move to another paragraph · P3 · new, open
D1352's mock shows the history entry of a drag to another paragraph with the object's name and the paragraph's ("Moved
Picture 1 to Paragraph 3"). The build uses the generic label "Moved an object" for every move. Belongs with UX-22 and
CODE-31 (how the history speaks). Related assumption of the same branch: a selection someone holds on an object still
names the paragraph the object was in before the move. **Acceptance.** The entry names the object and, when it changes,
the paragraph, in the user's language.

### PROC-40 · Four spec files run nowhere · P2 · new, open
**Measured** (2026-11-20): of the `.feature` files in `claudiaoffice-log/specs`, four are bound by no `scenarios(...)` in
`tests/e2e/specs/` and none of their scenarios has `@unit:`, `@io:` or `@e2e:`: `objects/names.feature` (28 scenarios,
`@pending:e1.13`), `container/requirements.feature` (6, `@pending:e1.9`), `invariants/objects-in-composes.feature` (12),
`computes/pictures-in-files.feature` (5). So they are not even counted as skipped: "all E2E specs pass" says nothing
about them. E1 is merged, so its `@pending` tags are also stale. **Fix.** A test in `tests/` that fails when a feature
file is neither bound nor has a test tag on every scenario; then bind the four (step code first for names and
requirements). **Acceptance.** That test, red today, green after.

### UX-61 · The access secret was called a recovery key · P3 · fixed 2026-11-20
Found while drawing the mock-up for SEC-12. `FirstAdminSetup.vue` said "The access secret you set earlier stays as a
recovery key — only needed if every administrator is ever locked out", and the hint under Access & documents began "A
recovery key, not needed day to day". The server has no recovery of administrators at all (today only deleting
`admins.json` in the state folder brings back the first-administrator page), and nobody signs in with the access
secret: it lets people make documents and read their list. **Fixed:** the setup page says to keep the password safe
and that only someone with access to the computer the server runs on can name a new first administrator (true now, and
with SEC-12's reset); the hint says what the secret does. German translations included. **Test:**
`web/tests/admin-wording.test.ts` (scenarios in `specs/server/administrators.feature`).

## Round of 2026-11-21 (the red CI after SEC-12, `main` at `2fc8b1b`)

The jobs "Python" (three systems) and "End to end (Chromium)" had been red since 2026-11-17 and 2026-11-20. Python had one cause (PROC-38). The end-to-end job was red because each first failure hid the one behind it: the Python step failed first, then `objects.cjs`, and the scripts after it had not run in CI for days. All of them were run on one computer in CI's order, with CI's fonts and hyphenation, and all pass now; the Python suite of `tests/e2e` too.

### UX-62 · ← and → did nothing on a selected object in composes · P3 · fixed 2026-11-21
The contract (`object-interaction-contract.md`, Arrow keys) says the arrow keys nudge a selected object and that in composes ↑↓ hang it from the previous or next paragraph and ←→ change its offset. ↑↓ were built; ←→ were not, and `objects.cjs` step 6 ("an arrow key nudges it") was red for composes. **Fixed.** ←→ move the object off the character it hangs from by 10 units, with Shift by 1, as in creates (D1390); the step is one constant for both apps now (`NUDGE`, `NUDGE_FINE` in `lib/geometry.ts`).

### PROC-41 · A launcher's server outlives the test that started it · P3 · fixed 2026-11-21
**Found** while reporting SEC-12 (a `claudia_server` was still there after the run of `tests/e2e`, with fonts and hyphenation folders): `test_computes_grid.py` starts `scripts/start.py`, which starts the server as its child, and killed only the launcher. **Fixed.** The process group is killed. After the run nothing is left.

### PROC-42 · The CI step for the Fonts script had no setup code · P2 · fixed 2026-11-21
My change for SEC-12 made the first administrator ask for the server's setup code. `scripts/run_e2e.py` was given it, the step "Server settings ▸ Fonts" of `ci.yml` was not: it would have been the next red step. **Fixed.** The step reads the code from `state-8768/admin/setup-code` (the file the server writes at its start).

### PROC-43 · Four stale lines in `objects.cjs` · P2 · fixed 2026-11-21
Behind UX-56 to UX-58 the script itself was out of date in four places, all made right **by the contract, not by the app's luck**: (1) *Proportions kept* was asked of every shape; a Rectangle has no aspect and may change its proportions (`null` in `shapes.py`), and creates only passed because its 3:2 shape moved by 2.6 %, under the 3 % allowed. It is asked of what shows corner handles only. (2) A table's menu is called "Table menu" (D1228, translated), not "Object menu". (3) `editable` for creates said every kind has words; a picture has none (D1225), and its menu already agreed. (4) After Delete the object leaves the screen at once and its history entry comes with the answer: the script waits for it (it failed one run in six). Business outcomes are as before.

## Round of 2026-11-21 (architecture improvements, branch `architecture-improvements`)

### CODE-75 · A viewer's change was sent in computes, and in creates only sometimes refused first · P3 · size 3 · fixed 2026-11-21
**Found** in the architecture review: composes refused every change of someone who may only look before sending it
(`denied()`, 33 places), creates checked `readOnly` in 9 places, computes in none, so a viewer's change in a workbook
went to the server and came back as `forbidden`. The words a person saw were the same; the round trip, the places that
were left out and the difference between the apps were not (the clients must not differ in function). Evidence: read,
then **measured**: `web/tests/object-layer-session.test.ts` fails on `main` for computes and creates. **Fixed.** Every
change goes through `BaseSession.write()`, which refuses before anything is sent (D1432). Escaped because: missing test
(each app's session was tested on its own).

### CODE-76 · The sheet session did not take in outlines · P3 · size 3 · fixed 2026-11-21
**Found** by the same test: the `shape` event was reduced by the text and the slide session, not by the sheet's. **Fixed**
with the one reducer of D1432. Escaped because: missing test (three copies of the reducer, each tested where it was).

### DOC-05 · The docs build failed on the asset store's type parameter · P3 · size 3 · fixed 2026-11-21
**Found** when the gate was run before the holder slice of E1.18: `docs` failed with ten warnings since `8874e30a` ("A
typed read-back in the asset store"), which made the store generic (`AssetStore[T: Asset]`). Sphinx links every type
in a signature (`nitpicky`), and `T` and the module's own protocol `Asset` are not documented classes. Evidence:
**measured** on the branch before any change of the slice. **Fixed.** Both are ignored in `docs/conf.py`, as the type
parameters `M` and `A` already are. Escaped because: test passed but wrong (the gate was run before that last commit).

## Round of 2026-11-22 (CI of `main` after merging `architecture-improvements`; the E6.31 mockups)

### PROC-45 · The Linux client's end-to-end test looked for the old paragraph attribute · P2 · size 3 · fixed 2026-11-22
**Found** in the CI of `main` after `architecture-improvements` was merged (run 45011761530): the job "Linux client
(Python 3.12, GTK 4)" failed on `test_composes_starts_its_server_shows_the_page_and_the_native_menu_drives_it` with
"gave up waiting for the text to take a word". The paragraph slice of E1.18 (D1430) renamed the attribute every
paragraph carries in the page from `data-block` to `data-paragraph`; the test's script still asked for `[data-block]`,
found nothing and never typed. Evidence: **measured**, red locally on `main` and green after the fix (713 passed, 6
skipped). **Fixed.** The selector names `[data-paragraph]`. Escaped because: test not run (the slice's gate does not run
the GTK client's tests, and GTK 4 and WebKitGTK were not installed in the agent's environment; they are now, as in CI).

### UX-68 · A sheet or a chart tab cannot be deleted in computes · P2 · size 2 · new, open
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

Found while the two dialogs were drawn in `penpot/claudia.penpot` from the running web app (screenshots of the live
dialogs next to the design). The Penpot file is not part of the bugs: it follows the app.

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

### UX-66 · A hard-coded colour in the Styles dialog · P3 · size 3 · new, open
**Read:** the `.flag` pill in `StylesDialog.vue` uses `color: #7a4710`, a literal that no token carries. The same
colour is `color.apricot-dark` in the Penpot design system, where it had to be mapped by hand. It will not follow a
theme change and is the same kind of fault as the 2026-11-06 contrast report. **Acceptance.** A test over the
dialogs' styles finds no colour literal outside `tokens.css`.

### UX-67 · Native selects in the Styles dialog · P3 · size 3 · new, open
**Read:** "Heading" and "Numbering" in the paragraph part of the style editor are native `<select>`s with the
browser's own look; the other controls (font, size, colour) are the app's own. Consistency fault, and a possible
BITV divergence (visible focus, contrast and target size of the native control were not tested). In the Penpot file
the control is drawn as the "Select / native" variant to show it. **Acceptance.** Either a decision that native
selects are the standard (and the other selects follow), or a styled select with the same keyboard behaviour; BITV
check of the result.
