# Merging `e1-core` and `e2-document-sec` into `main` (2026-11-20)

`e1-core` (19 commits) went into `main` as a fast-forward. `e2-document-sec` (7 commits) was merged on top; 16 files
conflicted. Both branches were based on the same `main` commit; `backlog` was already contained in `main`.

## How the conflicts were resolved

- **Code** (`app.py`, `composes.py`, `formats.py`, `hub.py`, `AdminApp.vue`, `ExportFormatDialog.vue`,
  `base-session.ts`): both sides kept. `export_office` of a text has E1's `description_comments` and E2's
  `leaves="export"`; `BaseSession.exportOffice` sends E1's parameters through E2's `recorded`; the export dialog
  offers E1's description-comments tick and E2's unencrypted format; the admin screen has E2's Security page and opens
  on Fonts for `#fonts` (E1).
- **`formats.import_state`** is now `(fmt, data, locale=DEFAULT_LOCALE, *, state_schema=None)`: E1's tests pass the
  locale positionally, so E2's `state_schema` became keyword-only. The upload desk passes both.
- **Translations**: `po/claudia.pot` was extracted again from the merged code, `po/de.po` is the union of both
  branches' German (no msgid was translated differently; all 2662 strings translated), `po/xx.po`, both `.mo` files
  and the web JSON catalogues were generated again.
- **`claudia-menus.xlsx`**: E1's version (row 96, widened duplicate-key formulas, Name & describe notes) with E2's
  four cells for File ▸ Print and File ▸ Export (rows 7 and 10) set on it. No cell was changed by both.
- **`ranges.md`**: E2's slice C claimed D1281–D1300 and E1 claimed D1300–D1329, and D1300 is used by E1. Slice C is
  narrowed to D1281–D1299 (it used D1281–D1285). No decision file id collides.
- **Server changelog**: E1's work stays under Unreleased, above E2's 0.39.0–0.41.0.

## What the merge had to add: E1's new requests under E2's viewer rule (D1261)

E2 requires every pushed event and every method to say which part of the document it shows, so that a viewer is given
the content only. E1's new event `thing_described` is content, like `thing_renamed`. E1's new methods
(`export_choices`, `font_report`, `name_and_describe`, `name_and_describe_range`, `thing_details` and the six what-if
methods) read the content and are listed in `tests/method_reads.json`.

One exception within a method: `what_if_start` with `at` starts a what-if from an earlier step, which is the history.
A viewer may still start a what-if of the document as it is now (D1308 lets her; she cannot write to it), but `at` is
refused to a role without the history key (`forbidden`), tested by
`test_a_viewer_cannot_start_a_what_if_from_an_earlier_step`. Without this, merging the two branches would have let a
viewer read any past state of the document through a what-if.

## Assumptions

- The classification above (content for E1's new methods and event; `at` history-only) is mine, made because the gate
  requires one; it follows D1261 and the existing table (`as_of` is history, `thing_renamed` is content).
