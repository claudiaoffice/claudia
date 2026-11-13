# The test-document library (D218)

Revisits the test-strategy discussion from before D217 now that a real import/edit/export path (docx) exists to
test against. The design question that drove this: once whole-file byte comparison is ruled out as unrealistic,
what replaces it, and how does visual comparison work with no PDF/print export yet?

## Three tiers, not one fuzzy check

Byte comparison is not abandoned, only narrowed to where it is actually the right check:

- **Tier 1 -- import / round trip.** `spec.py`'s `import_checks(model)` asserts facts about claudia's own model
  right after import; `after_checks(model)` (defaults to `import_checks`) asserts facts after an edit
  (`modify`) is applied, re-exported and reimported. No file comparison at all -- just calling the format's
  `docx_to_text`-equivalent and checking the model.
- **Tier 2 -- preserve.** For content claudia does not model (a table, an image), nothing in Tier 1 can assert
  anything, so this checks the *bytes that should not have moved*, at whichever granularity actually matches
  where the content lives: `preserve_parts` (a whole package part byte-identical -- `word/media/image1.png`)
  for content with its own part, `preserve_elements` (one element's own serialized XML byte-identical, via the
  library's own object model) for content sharing a part with something the edit does rewrite (a table inside
  `word/document.xml`). `export_checks` is the third member of this family, for the opposite problem: a feature
  the model layer cannot see back out again at all (a tracked change -- `docx_to_text` cannot reimport one,
  python-docx's own `paragraph.text` already skips it), checked against the raw re-exported bytes directly
  instead of a reimported model.
- **Tier 3 -- visual, opt-in (`--visual`).** A backstop for a property with no structural oracle at all --
  layout, a pivot table's rendered shape -- not a replacement for Tier 2 (byte-identical is strictly stronger
  than any pixel comparison). `claudia_test_documents.render` shells out to headless LibreOffice
  (`soffice --headless --convert-to png`) to rasterize both files' first page -- claudia's own, nonexistent,
  export pipeline is not involved in the rendering at all, which is what sidesteps "there is no PDF export yet"
  -- then compares with a crude Pillow-only perceptual diff (mean pixel difference, normalized, against a
  tolerance; no SSIM, no new dependency beyond Pillow, already in the workspace via python-pptx). **No current
  catalogue entry opts into this** (`Case.visual = True`): none of the four has a property that is only
  checkable by looking at it, which is itself a useful finding -- it means Tiers 1-2 are doing the real work, as
  intended. The mechanism is built, wired into the runner, and its comparison logic (`perceptual_difference`) is
  unit-tested; `render_first_page`'s own `soffice` call is not (environment-dependent, and nothing exercises it
  yet) -- manually smoke-tested once by temporarily opting a real fixture in, not kept in the repo.

## The catalogue

`test-documents/catalogue.json` is the one file deciding what actually runs: a `source.docx`/`spec.py` pair on
disk with no entry is staged, not wired in. Two writers, two disjoint sets of fields -- a person hand-edits
`id`/`format`/`feature`/`source`/`spec`/`summary`/`backlog`/`tags`/`enabled`; only `scripts/run_test_documents.py`
writes `last_run` (timestamp, commit, overall status, per-stage status, duration, detail), and only for the
entries a given run actually covered, so `--format docx` does not stamp every other entry "not run this time".

`claudia_test_documents.catalogue.save` always rewrites the whole file (plain `json.dump`, not a surgical text
patch) -- safe for the hand-written fields because `record_run` only ever mutates the `last_run` key of the one
entry a run covered in memory, before anything is written back.

## Running it

`scripts/run_test_documents.py`: `--format`/`--feature`/`--id`/`--tag` (repeatable, AND together), `--visual`,
`--report` (prints current `last_run` status, runs nothing), `--no-write` (prints results without touching the
catalogue), `--fail-fast`. Exits non-zero on any failure. Deliberately a separate script, not folded into
`scripts/check_debt.py` -- Tier 3 needs `soffice` and is slow, and nothing here should become something every
`pytest` run pays for.

`tests/test_test_documents_catalogue.py` runs every enabled entry (Tiers 1-2, `visual=False`, no write-back) as
one parametrized test per entry, so it is part of the normal gate without needing `soffice` or writing to a
file a person hand-maintains. This is the one place the catalogue's `last_run` and the actual pass/fail of the
gate can disagree momentarily -- a run via the CLI script updates `last_run`; the gate test is the ground truth
of whether the suite currently passes.

## `claudia_test_documents` package

- `case.py` -- `Case`: every field optional (a "beyond claudia" case defines no `import_checks` at all).
- `adapters.py` -- `Adapter` (`import_fn`, `apply_edits_fn | None`) and `ADAPTERS`, one entry per format with a
  real import/export path. Only `docx` is registered; a format with no `apply_edits_fn` yet is not an error --
  `run_case` reports its round-trip and preserve stages `"skipped"`, so the catalogue can grow with each
  format's own real work instead of waiting for all of them.
- `loader.py` -- `load_case`: every `spec.py` is named the same on purpose (browsing the library, not Python's
  import system, is what the directory layout is for), so each is loaded by its own path with a name derived
  from the catalogue id, never a plain `import spec` that would alias every entry to whichever loaded first.
- `catalogue.py` -- `load`/`save`/`select`/`record_run`, plain `dict`-shaped entries (no dataclass
  wrapper: the whole point is that this is also just JSON a person edits by hand).
- `runner.py` -- `run_case`: never raises for a finding about the test case itself (a failed assertion or a
  missing adapter capability is a stage result); a genuinely broken `spec.py` or a missing source file does
  raise, since those are setup bugs, not findings.
- `render.py` -- Tier 3, described above.

## The four docx fixtures

Generated by `test-documents/_build_fixtures.py` (python-docx), not hand-authored binaries -- a deliberate
departure from this repo's usual every-format-test-builds-its-document-in-Python convention, because the whole
point of a *library* is real, openable files (LibreOffice, real Word), not just assertions about one; the
generator ships alongside so nobody has to hand-edit a `.docx` to change or extend a fixture.

- `heading-styles` -- Title/Heading 1/Heading 2 map to claudia's style ids; editing one paragraph's text leaves
  every other paragraph, and its own style, alone (Tier 1).
- `tracked-change-suggestion` -- a plain-text coworker file gets an open suggestion added in claudia and
  re-exported as a real `w:ins`/`w:del` pair; `export_checks` reads the exported XML directly, since
  `docx_to_text` cannot reimport a tracked change by design (Tier 1 + the `export_checks` member of Tier 2).
- `beyond-claudia/table` -- a table claudia has no model for at all, sitting inside the same part
  (`word/document.xml`) an edit rewrites; `preserve_elements` asserts the table's own `_tbl.xml` is
  byte-identical while the surrounding paragraph changes (Tier 2, element-level).
- `beyond-claudia/image` -- an embedded image in its own package part (`word/media/image1.png`); `preserve_parts`
  asserts it is byte-identical through an edit to a different paragraph (Tier 2, part-level) -- the other half
  of the mechanic the table fixture does not exercise.

## Not done, on purpose

- Only docx is catalogued -- xlsx/pptx/odt/ods/odp have no `apply_edits_fn` yet (D135 covers base export only),
  so there is nothing for Tier 2/round-trip to run against until each gets its own D217-equivalent.
- No case opts into Tier 3 yet (see above) -- kept honest rather than contrived, until a feature actually needs
  it (layout, a pivot table's rendered shape, a transition).
- The "venn diagram" angle from the original test-strategy discussion (content inside LibreOffice/MS Office's
  feature set but outside both the real app *and* claudia's model, as opposed to "beyond claudia" alone) is not
  separately represented yet -- the two `beyond-claudia` fixtures cover "claudia cannot model this", not yet
  "nor can any format converter get it wrong in a specific, known way".
