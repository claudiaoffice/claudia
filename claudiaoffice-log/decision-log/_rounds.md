# Decision log: rounds and history

The prose that sat between the tables of the old single-file `decision-log.md`, in its original order: the vision statement, why rounds happened, and the renumbering passes. Each decision itself is a file in this folder; the list under each round says which. Rarely needed day to day.

## Renumbering, 2026-11-05 (read this first)

Three documents allocated D-numbers independently and two blocks collided: `decision-log.md`, the Epic 2 container
design, and the Linux client notes each used **D70–D82** and **D97–D99** for different decisions. The collision was
live in the source as well as in the documents (`claudia_container/crypto.py` cites D74 meaning the cryptographic
primitives, while `claudia_server/composes.py` cites D75 meaning the styling details).

Resolved as follows: this log keeps the product numbering, because it was first and is cited most widely. The other
two blocks were renumbered into free space, and the mapping is kept here permanently so an old reference still
resolves. **The code has not been updated yet** — that is tracked as DOC-01 in `bugtracker.md`.

| Old number, in that document | Subject | New number |
| E2 design D70 | Threat model | **D100** |
| E2 design D71 | Key hierarchy | **D101** |
| E2 design D72 | User names not visible in the file | **D102** |
| E2 design D73 | Readable without a password | **D103** |
| E2 design D74 | Primitives: Argon2id, HKDF, AES-256-GCM | **D104** |
| E2 design D75 | Recovery key | **D105** |
| E2 design D76 | Write path: journal, group commit, one file | **D106** |
| E2 design D77 | New package `claudia-container` | **D107** |
| E2 design D78 | Unencrypted export and import | **D108** |
| E2 design D79 | Password rules | **D109** |
| E2 design D80 | What an encrypted download contains | **D110** |
| E2 design D81 | Viewers see the names of all users | **D111** |
| E2 design D82 | File extension `.claudia` | **D112** |
| Linux client D97 | Layout of the native clients | **D113** |
| Linux client D98 | Shell contract is a versioned JSON schema | **D114** |
| Linux client D99 | The Linux shell serves a local server | **D115** |
| Linux client D100 | Shell on 3.12, server on 3.14 | **D116** |
| Linux client D101 | Page adapter instead of changing the web app | **D117** |
| Linux client D102 | Rules of the web view in every shell | **D118** |
| Linux client D103 | The server never outlives its shell | **D119** |

## Vision

> Claudia is a privacy-first office suite of three quiet, elegant apps (composes, computes and creates) that you can
> run on your own hardware. Documents live on a server you choose, are shared live with colleagues, and an AI that runs
> where you decide works in the document as one more participant, bound by the same rules as everyone else. The
> interface stays out of the way and keeps its power in menus and context. The goal is to help people think with their
> data and ideas, not only record them.

Design character: a hint of female elegance, technical precision, technical power. Inspiration: Bret Victor
(co-thinking, understanding through interaction, visualization and simulation).

A proposed addition about stories across the three apps is in `notes/product-vision.md`; it is not part of the
statement until the owner agrees.

## Product and UX

Decisions: D1, D2, D3, D4, D5, D6, D7

## Architecture

Decisions: D8, D9, D10, D11, D12, D13, D14, D15, D16, D17, D18

## Common to all three apps

Decisions: D19, D20, D21, D22, D23, D24, D25, D26, D27, D28, D29, D30, D31, D32, D33

## Security, calculation and extensibility (second round)

Decisions: D34, D35, D36, D37, D38

## Repository (third round)

Decisions: D39

## Web views and the panel (fourth round)

Decisions: D40, D41, D42, D43, D44

## Kernel and server (sixth round)

Details: `notes/e1-kernel.md`.

Decisions: D45, D46, D47, D48, D49, D50

## Live sessions (seventh round)

Decisions: D51, D52

## Menus and documents (eighth round)

Decisions: D53, D54

## Demo v0 (ninth round)

Decisions: D55, D56, D57

## Stories across the suite (tenth round)

Reasoning and the owner's own pictures: `notes/product-vision.md`.

Decisions: D58, D59, D60, D61, D62, D63, D64, D65, D66, D67, D68, D69

## Answers to the vision round (eleventh round)

Decisions: D70, D71, D72

## Styling and Edit menu (twelfth round)

Decisions: D73, D74, D75

## Help system (thirteenth round)

Decisions: D76

## Claudia creates, first draft (fourteenth round)

Decisions: D77, D78, D79, D80, D81, D82, D83, D84, D85

## Bibliography and full LaTeX (fifteenth round)

Decisions: D86, D87, D88

## Fonts and typesetting services (sixteenth round)

Details: `notes/e3-fonts-and-typesetting.md`.

Decisions: D89, D90, D91, D92, D93, D94, D95, D96, D97, D98, D99

## Document container and encryption (seventeenth round)

Renumbered from the E2 design document's D70–D82 (see the table at the top). Details:
`notes/e2-container-and-encryption.md`.

Decisions: D100, D101, D102, D103, D104, D105, D106, D107, D108, D109, D110, D111, D112

## Native clients (eighteenth round)

Renumbered from the Linux client notes' D97–D103 (see the table at the top). Details: `notes/e5-linux-client.md`.

Decisions: D113, D114, D115, D116, D117, D118, D119

## Menu redesign and accessibility baseline (nineteenth round)

Screens only so far (`notes/mockups/`, `notes/e5-1-e5-10-menus-and-accessibility.md`); nothing below is built. Scope
agreed with the owner 2026-11-05, before the screens themselves were reviewed.


The owner's first look at the screens (same day) settled most of what D120 had left open:


The owner then asked whether computes' Edit menu, grown long with row/column actions, should group them:


The owner ran the applied patch in dark mode a second time and reported a further, larger round of contrast and
boundary bugs. Asked for design suggestions before any code; two choices were put to the owner and answered:

Decisions: D120, D121, D122, D123, D124, D125, D126, D127, D128, D129, D130, D131, D132

## Quality gate truthfulness (twentieth round)

QA review of code quality and technical debt (PROC-02, PROC-03, DOC-01, CODE-07, CODE-08). Three of the project's own
quality signals — the gate, a note, the decision log's own numbering — turned out to say things that were not true,
each found by accident rather than by a check that was looking for it.

Decisions: D133

## Worker pool placement (twenty-first round)

QA (PERF-01/02/05) found `Connection.handle` running every request on the event loop: two O(sheet-size) hot paths
(the `_cells` grid-window query and the sheets' `_extent`) and `_cells.py`'s synchronous `os.fsync` each stall every
document the process holds. The fsync fix and the O(sheet-size) fix are both below; this round is about the worker
pool that D37 already specified for the fsync tier (and that E4.3/E4.4/E4.9/E3.4 are blocked on) but that was never
built. Raised by the owner: "where should we locate the worker pool and multi processing? I think it best to have it
in the core, so it can be re-used in any of the three apps." Discussed and agreed before building.


Separately, the O(sheet-size) cost itself (PERF-01/05) was fixed without a worker pool: `_cells`/`_extent` moved from a
full scan to an index (sparse row→sorted-columns map, plus lazy-deletion max-heaps for the row/column extent)
maintained incrementally at `WorkbookModel.store()`'s single per-cell mutation point, falling back to the existing
O(sheet-size) rebuild only for structural edits and document load. An invalidate-and-rebuild cache was considered and
rejected: the measured workload interleaves edits and window queries closely enough (a user scrolling while another
edits) that a rebuild-on-next-read would frequently pay the full O(sheet-size) cost anyway, with none of the
incremental approach's guarantee that cost tracks the window, not the sheet.

Decisions: D134

## Row height and column width (twenty-second round)

Decisions: D135, D215

## The Manage menu: leaving, handing over ownership, exporting and deleting (twenty-third round)

Stories E2.3 (leave or remove a collaborator) and E2.9 (export). Built in full — not a mockup — for all three apps, on
the server, the web client and the Linux shell, from a fresh `main` checkout, as a patch for the owner to apply.

Decisions: D141, D142, D143, D144, D145, D146

## Additive xlsx/docx/pptx extensions (twenty-fourth round)

Closing a separate gap found while looking at import/export: each app's own format library writes a correct base
file but cannot write everything the app's model can hold (a pivot table, a tracked change, a slide transition).

Decisions: D147

## Decision-number renumbering, second pass (QA review, 2026-11-07)

`D135` had been independently allocated three times by three branches merged in parallel — Row height and column
width, The Manage menu, and Additive xlsx/docx/pptx extensions — the exact DOC-01 shape D100–D119's renumbering was
meant to close for good, recurring one merge later. Two further pending notes (not yet applied when found, in
`claudiaoffice-log/tmp/`) had each separately picked `D141` next, for two unrelated things, for the same reason:
neither branch could see the other's pick. **Kept as `D135`:** row height and column width (the oldest, most-cited
claim). **Renumbered:** The Manage menu's block (was D135–D140) to **D141–D146**, sequentially, so its own table
stays internally ordered; Additive xlsx/docx/pptx (was D135) to **D147**. Every citation in source — `claudia_server`,
`clients/linux`, the five `web/app/components/*Dialog.vue` files, `docs/server.md`, the three new `-io` packages —
updated to match. The restore-with-consent and i18n-groundwork rounds below were written after this pass, directly
at their final numbers (D148–D150), so they never collided in the first place.

## Internationalization groundwork (twenty-fifth round)

The groundwork for E5.7 (D31), not the full epic: no interface string has moved into a catalog yet, by design — the
plumbing is proven first, with an (almost) empty catalog, so moving real strings later is mechanical.

Decisions: D148

## Restore with consent, and the line picker (twenty-sixth round)

Building E3.7/E3.8 together: a live session's consent flow for restoring a checkpoint or switching to a hidden
line, and a first version of the picker that surfaces those lines. Two decisions, agreed with the owner before
building.

Decisions: D149, D150, D214

## Server administrators and settings (twenty-seventh round)

Building the backend half of server configuration: who may configure a server, and what they can set. The frontend
(settings dialogs, the Open dialog's gear icon, the TopBar indicator) is a separate patch, deliberately deferred
until the owner has looked at this one.

Decisions: D151, D152, D153, D154, D155

## Neutralino on Windows and macOS (twenty-eighth round)

The owner ran the Neutralino spike (`spikes/e0-3-neutralino/`) on a Mac and on Windows 11. Evidence and what is still
untested: `notes/e0-3-neutralino-windows-macos.md`. The four entries below were **proposals** (Claude's suggestion, not
yet agreed) when written; they followed from what was seen and decided nothing about the Linux shell.

**Update, 2026-11-07 (E5.11):** the first macOS client (`macos-client:clients/macos/`, `notes/e5-11-macos-client.md`) was built
against D157–D159. D159 is no longer a proposal: the owner answered it explicitly (`AskUserQuestion`). D157 and D158
gained evidence from what was actually built but are not themselves confirmed by the owner, so they keep their
"Proposal" tag; what changed is appended to each entry's Notes. D158's `role` field also did, for the first time,
touch the *shared* manifest (`clients/linux/src/claudia_shell_gtk/manifest.py`) rather than staying confined to a
macOS-only file — additive, and GTK ignores the field, but the preamble above no longer holds literally.

Decisions: D156, D157, D158, D159, D161, D216

## App Language, the first real catalog (twenty-ninth round)

The owner's second i18n round: not more plumbing (D148 already built that), but the first real, visible use of
it — a working `Config ▸ App Language` switch, in both shells, with a real German translation behind it.

Decisions: D160

## Server settings, frontend half (thirtieth round)

The frontend patch the twenty-seventh round's note deferred: the settings pages themselves, the Open dialog's server
bookmarks sidebar, and the TopBar's connection indicator, on top of the already-built backend (D151–D155). Three
questions (server label, routing, scope) were settled with the owner via `AskUserQuestion` before building; the rest
follow from reading the real backend surface rather than the mockups' more aspirational version of it.





**Numbering note, found while merging `main` into this branch (2026-11-08):** two ID collisions already exist on `main`, from branches that diverged before either side had the other's new entries — `D151` (this branch's "Administrator accounts are a separate, server-scoped identity…", twenty-seventh round) collides with grid-in-creates' "A grid overlay in creates…"; `D160` (row/column resize, twenty-second round) collides with this round's own original numbering before it was shifted above. Left as-is here, since neither is this patch's to renumber — flagged for whoever next does a renumbering pass (precedent: "Decision-number renumbering, second pass (QA review, 2026-11-07)").

Decisions: D168, D169, D170, D171, D172, D173, D174, D175, D176

## Shapes, images and styles: one shared object layer (thirty-first round)

**Found while doing this (not a decision, a bug this round fixed):** creates' built-in styles had never been validated. Its own `Style` dataclass did no checking, and one font name in `body-text` — `-apple-system` — is in fact refused by `claudia_core`'s `ALLOWED_CSS` (a font name may not start with a hyphen). Routing the styles through a real `StyleBook` caught it on the first import; the stack is now the same one composes uses.

Decisions: D177, D178, D179

## PNG, and an object's words as a paragraph (thirty-second round)

Decisions: D180, D181, D182

## Colour roles: the document's palette (thirty-third round)

Numbered from **D200** on purpose. The `worker-pool` branch has independently allocated D177–D179 for unrelated
decisions while this branch used the same numbers, so this round leaves a gap no live branch can reach rather than
adding a third collision to the two this log already carries (D151, D160). The owner chose this on 2026-11-08.

Decisions: D200, D201, D202, D203

## Computes charts: the diagram/chart RPC surface and the Plotly UI (thirty-fourth round)

Decisions: D204, D205, D206, D207

## Charts: an explicit header-row toggle, after a reported bug (thirty-fifth round)

Decisions: D208

## The styling dialogs: one menu, three apps (thirty-sixth round)

Decisions: D209, D210, D211

## Word, Excel and PowerPoint out of every app, and pictures in a PowerPoint (thirty-seventh round)

Decisions: D212, D213

## Real import, edit and re-export: docx, pptx, xlsx, and the test-document library

These four decisions were written on `xlsx-docx-pptx-additive-io` and appended to the log at the end of the thirtieth round; they had no round heading of their own.

Decisions: D217, D218, D219, D220

## One file per decision (2026-11-10)

The single file `decision-log.md` became this folder: one file per decision, its status and the app it applies to
in the file name (`README.md`). Done in one pass with the backlog, which became one file per story under
`Projects/claudia-office/_tasks/`. Along the way:

* **Six numbers that meant two things were split.** The block cited as a range keeps its number; the other entry
  moved, and every citation in the code, the docs and the notes was rewritten by its context:

  | Was | Meaning | Now |
  |---|---|---|
  | D151 | a grid overlay in creates, and snapping to it | **D214** (D151 stays: administrator accounts, D151–D155) |
  | D160 | resizing a multi-line selection by percentage | **D215** (D160 stays: Config ▸ App Language) |
  | D160 | Windows needs no `file-dialog.ts` (proposal) | **D216** |
  | D177 | `claudia-opc-io` and the real docx round trip | **D217** (D177 stays: the shared object layer, D177–D182) |
  | D178 | the test-document library | **D218** (D178 stays: a shape's SVG style vocabulary) |
  | D179 | pptx import, edit and re-export | **D219** (D179 stays: composes objects follow the text) |
  | D204 | xlsx import, edit and re-export | **D220** (D204 stays: chart definitions, D204–D208) |

  Sentences in the implementation notes that describe the collisions themselves keep the old numbers on purpose.
* **D163** was still cited in `ConnectionIndicator.vue` and `connection.ts` for "Manage this server… is always
  shown". That round's decisions had been renumbered D162–D167 → D170–D175 when it was merged; the citations now say
  D171.
* **The "Open design questions"** became D221–D240, each `undecided` or `blocking`.
* **Statuses** were read from the log's own words: D4 (superseded by D120), D117 (by D121) and D125 (by D209) are
  superseded; "partly superseded" (D41, D50, D90) stays current. The entries still written as unconfirmed proposals
  (D156–D158, D161, D216, and D130) were put to the owner, who confirmed them all as current, since the code follows
  them. Of the former open questions, the owner marked D228, D229, D230 and D231 as blocking; the rest are
  undecided.

## Real-world documents (branch `real-world-docs`, 2026-11-13)

The owner supplied five real documents (two Excel workbooks, a PowerPoint deck, an old Word form, an OpenDocument
letter) and asked what Claudia needs to open, edit and save them. They stay out of the repository. The first patch makes
xlsx files as today's Excel writes them open and survive an edit; the second draws the screens for templates and
layouts in creates (E10.4); the third brings cell formats and number formats (E6.14, E6.18).

Decisions: D370, D371, D372 (xlsx); D373, D374, D375, D376 (templates in creates: proposals awaiting the owner); D377 (dates and money); D378, D379 (number formats; cell formats as styles); D380 (changed looks in an edited file)
