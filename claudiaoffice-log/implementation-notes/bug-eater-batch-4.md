# Implementation note: bug eater, batch 4

Written 2026-11-25, branch `batch-4` (from `main` at `a2e9cf1f`, `main` merged again at `e3c6c688`). The brief is
`notes/bug-eater.md`. The owner approved the batch: UX-70 (with panel B of `notes/mockups/export-dialog-tracked-changes.svg`
as drawn), CODE-25, CODE-66, CODE-70, CODE-47 (D2004), PROC-37 (option (a), D2005), CODE-45 (size 1, kept in this batch),
UX-90, PROC-62, and drafts of the computes and creates invariants for review. UX-91 stays out. Two helpers worked in
worktrees of their own (CODE-66 and CODE-70; CODE-47 and PROC-37); their commits were taken over one by one. One commit
per item, its message starting with the item's ID.

## What changed, per item

| Item | Change | Test written first (seen red) |
|---|---|---|
| CODE-25 | pptx and odp write and read what the slides and objects are called (`p:cNvPr/@name`, `p:cSld/@name`, `draw:name`), told apart as `Name (2)` when a file calls two things the same (`_names.FileNames`); a page called `page<n>` has no name; a picture's file name stays apart from its name | `test_pptx.py`, `test_odp.py`: round trip, duplicates, the patch of a kept file, a picture's name |
| UX-70 | After an export the dialog says, one line per kind, what the file does not hold and why or what to do, then "Everything else is in the file." (or "Everything is in the file."), in a `role=status` region that is always there. The words of every code are in `lib/export-losses.ts`; the codes of a kept file (`not-patched`, `removed-…`, `stale-reference`) too; a code nobody has worded is said with its code | `web/tests/export-losses.test.ts` (the module did not exist); `tests/test_loss_words.py`, a guard that every code the Python sources report on an export has words (it found the three kept-file codes) |
| CODE-45 | A title, subtitle or body placeholder with words is a text box in its layout's place and size; the title's words in the theme's heading font; a body's first paragraph takes its master's bullet (read through the layout's and the master's list styles, `_pptx_placeholders.py`). An empty placeholder (or one of spaces) shows nothing and is no loss; a footer, date or slide number stays `object`. The patch keeps the placeholder and writes `buNone` when a bullet is taken away | `test_pptx.py`: five tests on a "Title and Content" deck (no objects came in); the `buNone` test was seen red with that line taken out |
| UX-90 | 28 `role="status"` regions in 23 components (one bound: `ContainerFace.vue`) are on the page before what they say; the condition moved inside. An empty one takes no room (`[role="status"]:empty { position: absolute }`, not hidden) | `web/tests/live-regions.test.ts`: reads every template with Vue's parser (27 found, then the bound one) |
| PROC-62 | The file tests wait until the core has answered (`vi.waitFor`, 5 s), not 10 ms | reproduced with no time to settle: four tests failed, this one as on CI |
| CODE-66 | The patch of a kept xlsx or ods adds, moves, turns, renames, describes and removes pictures (`xlsx_picture_patch.py`, `ods_picture_patch.py`); `pictures` counts as written for a kept file | `test_pictures.py`: each case reported `object` before |
| CODE-70 | The patch writes the pivots defined since the import with the fresh export's own writers (`put_pivots`, `data_pilot_tables`); one of the file's own that was changed or removed is still reported | `test_xlsx_pivots.py`, `test_ods_pivots.py` |
| PROC-37 | D2005: an owner's export that comes back in brings the history of the original as one read-only note of the import step (`Import.original`): a line per step and per chat message for everybody, private ones left out. Shown folded under the import ("History of the original"), also after a partial redaction | `test_server_export_import.py` (`KeyError: 'original'`, `'with_history'`) |
| CODE-47 | Not built: D2004 needs words with a style of their own inside a paragraph, which composes does not have (a paragraph has one style; runs say only who wrote what). See below | (analysis) |
| (drafts) | `specs/invariants/objects-in-computes.feature`, `objects-in-creates.feature` with `objects-in-computes-and-creates.review.md`; `specs/document-file/what-a-file-does-not-hold.feature` (UX-70). All `@draft`: nothing runs them before approval | – |

The code review (two reviewers: standards, spec) found: suppressions without a reason, a duplicated `_pictures`, a bound
status role the guard missed, the note hidden after a partial redaction, a placeholder of spaces read as a text box, an
unworded `removed-…` member shown as its raw code, a stale comment and "download" for "export" in the drafts. All fixed
on `batch-4` (one commit per item).

**Versions:** additions under *Unreleased* in the changelogs of claudia-creates-io, -computes-io, -core and -server; the
API snapshot regenerated for PROC-37; versions are raised at release, as the repository does.

## CODE-47: what D2004 needs (the owner decides)

A paragraph of composes has exactly one style; its `runs` only record who wrote what, and only paragraph styles exist
(D306's marks were never built). To give words their own font, as D379 does for cells, composes needs styled stretches
inside a paragraph that split and join on typing like `runs`, a style kind for words and a command to set it, and the
layout, renderers, docx and odt readers and writers, copy and paste and the editor to follow. A smaller step fits today's
model: when every run of a paragraph has the same font of its own, a provisional paragraph style "Body text · Georgia"
(D379's idea). Words in another font inside a paragraph would still be a `formatting` loss, as now.

## Assumptions

- CODE-25: PowerPoint's automatic names ("TextBox 3", "Title 1") come in as the objects' names: they are what PowerPoint
  shows in its selection pane. LibreOffice names no shape; a page it calls `page<n>` is read as no name.
- CODE-45: only the first paragraph of a body takes its bullet (the model holds one paragraph per box, as for a text box);
  the size and alignment a placeholder inherits are not read (see CODE-101 below). A picture placeholder stays `object`.
- UX-70: a count is said as "(n)" after the line, so no line needs a plural form; the reason a kept file was written anew
  (`not-patched`'s detail) is an English developer sentence and is not shown.
- UX-90: `role="alert"` is left as it is. A region that comes with a whole new view (a dialog, the chosen-file part of
  the Import dialog) is read with that view.
- CODE-66 (helper): computes cannot move an object to another sheet, so the patch does not either; a picture cleared of
  its name is written as "Picture" in xlsx; an SVG added to a kept file is written as its fallback (`svg-fallback`).
- CODE-70 (helper): a new pivot's name could clash with a pivot in the file that the model did not take in; the file's
  pivot caches are marked to refresh on open when one is added.
- PROC-37 (helper): steps of every branch, ordered by time; an undo or redo step is "undo · …" as the panel says it; a
  redacted chat message keeps its line without words; the note has no size cap.

## Found in this batch (proposed IDs, not logged yet)

| ID | Size | What | How known |
|---|---|---|---|
| CODE-101 | 2 | A pptx placeholder's inherited size and alignment (a title's 44 pt, centred) are neither read nor reported | read, while fixing CODE-45 |
| CODE-102 | 2 | A pptx box with several bulleted paragraphs comes in with one bullet (the model has one paragraph per box), and no loss says so | read; common now that bodies come in |
| UX-92 | 3 | History & Chat says "undo" and "redo" in English before a step (and the original's note copies it) | read (`SidePanel.vue`) |
| CODE-103 | 3 | ods chart patch: a chart in a cell that is moved and described in one export makes overlapping edits, so the file is written anew | read (helper) |
| CODE-104 | 3 | Pictures of an xlsx that LibreOffice wrote are not read in, nor turned ones of such an ods | measured (helper) |
| SEC-24 | 2 | An owner's export writes every chat message, also private ones between other people she cannot read | read (helper) |
| SEC-25 | 2 | An editor can send a whole `core.Import` through `apply` and replace the document (or forge a note) | read (helper) |
| CODE-105 | 3 | docx: a paragraph mark's own run properties count as a `formatting` loss, though nothing is lost | measured (helper) |

## Say what could not be run

- Firefox (it cannot be installed here): CI's Firefox job is the check.
- A screen reader: UX-70 and UX-90 are checked through the accessibility tree and the templates only.
- Windows (PROC-62's flake): the tests were run ten times on Linux; CI's Windows job is the check.
- PowerPoint itself: CODE-45 and CODE-25 were checked with python-pptx reading the files back, not in PowerPoint.
- The desktop clients by hand; they load the web app (the Linux client's tests and the Neutralino tests ran).
