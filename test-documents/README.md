# The test-document library (D178)

A catalogue of real office files, organized by format and feature, run through claudia's own import/edit/export
path and checked three ways -- not by comparing bytes of the whole file (unrealistic: a library's own `save()`
rewrites things claudia never touched, for reasons that have nothing to do with correctness), but by comparing
the right *thing* at each stage:

1. **Import** -- facts about claudia's own model, right after import (`spec.py`'s `import_checks`).
2. **Round trip** -- the same facts (or different ones, via `after_checks`) after an edit is applied and the
   file is re-exported and reimported; for content the model layer cannot see back out again (a tracked
   change), `export_checks` looks at the raw re-exported bytes instead.
3. **Preserve** -- content claudia does not model at all (a table, an image) must survive the same edit-and-
   reexport loop untouched: either a whole package part stays byte-identical (`preserve_parts`), or, for
   content sharing a part with something the edit does rewrite, a specific element's own serialized XML does
   (`preserve_elements`).

A fourth, opt-in tier (`visual: True` on a `Case`, run with `--visual`) renders both files with headless
LibreOffice and compares them perceptually -- reserved for a property that is only checkable by looking at it
(layout, a pivot table's rendered shape); no case needs it yet, see `claudiaoffice-log/implementation-notes/`.

## Layout

```
test-documents/
  catalogue.json          the list of what actually gets tested -- see below
  _build_fixtures.py       regenerates every source.docx deterministically
  docx/
    heading-styles/
      source.docx          a real, openable file
      spec.py               its Case
    beyond-claudia/
      table/
        source.docx
        spec.py
```

A `source.<ext>`/`spec.py` pair with no entry in `catalogue.json` is not part of the library -- staged, not
wired in. `catalogue.json` is the one file to edit by hand (every field except `last_run`, which only a run of
`scripts/run_test_documents.py` ever writes, and only for the entries that run covered).

## Running it

```
uv run python scripts/run_test_documents.py                      # every enabled entry
uv run python scripts/run_test_documents.py --format docx
uv run python scripts/run_test_documents.py --feature beyond-claudia/table
uv run python scripts/run_test_documents.py --id docx-heading-styles
uv run python scripts/run_test_documents.py --tag beyond-claudia
uv run python scripts/run_test_documents.py --visual              # also runs the slow Tier 3 pass
uv run python scripts/run_test_documents.py --report              # prints current status, runs nothing
uv run python scripts/run_test_documents.py --no-write            # prints results without touching catalogue.json
```

Exits non-zero if anything it ran failed. Every enabled entry also runs as part of the normal `pytest` gate
(`tests/test_test_documents_catalogue.py`, Tiers 1-2 only, no write-back) -- the CLI is for a person running it
on purpose and updating the catalogue's own record of how it went, not for CI's fast loop.

## Adding a case

1. Add a `build_<name>()` function to `_build_fixtures.py` (python-docx, or whichever library the format uses)
   and run it to write `source.<ext>` -- or, for content no builder function can produce cleanly, author the
   file by hand in the real application and drop it in.
2. Write `spec.py` next to it: `from claudia_test_documents.case import Case`, then whichever of
   `import_checks`/`modify`/`after_checks`/`export_checks`/`preserve_parts`/`preserve_elements` the feature
   actually needs -- a "beyond claudia" case defines no `import_checks` at all, since claudia has nothing to
   assert about content it does not model.
3. Add an entry to `catalogue.json`: `id`, `format`, `feature`, `source`, `spec`, a `summary` of what it is
   actually testing and why, the backlog epic it belongs to, and `tags`.
4. Run `uv run python scripts/run_test_documents.py --id <your-id>` to see it recorded.

A format with no `apply_edits_fn` yet (everything except docx, today -- see
`claudia_test_documents.adapters.ADAPTERS`) can still be catalogued for Tier 1: the round-trip and preserve
stages come back `"skipped"`, not failed, until that format gets its own real edit-and-reexport path.
