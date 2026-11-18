# Changelog of claudia-test-documents

Newest first. The format follows [Keep a Changelog](https://keepachangelog.com/); versions follow the versioning
policy (`docs/versioning.md`). While the major version is 0, a minor version may break the API.

## [0.3.0] - 2026-11-18

### Added
- Running a folder of documents that have no `spec.py` -- a corpus kept outside the repository, such as Apache POI's
  or LibreOffice's own test files. `discover_corpus` finds every file of a supported format; `run_corpus_file` and
  `run_corpus` check each one the same three generic ways (it imports; a no-op edit re-exported and re-imported leaves
  the model as it was; no package part goes missing), giving a `CorpusResult` with the status `pass`, `fail`,
  `error` or `rejected` (not a readable package, or over the safety limits: correct, not a finding);
  `summarize_corpus` counts them and `write_corpus_report` writes a JSON file that two runs can be diffed by.
  `scripts/run_test_documents.py --corpus DIR` is the command line for it.

## [0.2.0] - 2026-11-11

### Added
- `ADAPTERS["odt"]`: odt cases run through import, edit-and-reexport and preservation like docx, pptx and xlsx (D401).
  The library gains six odt cases: three files written by LibreOffice itself, three made by `_build_fixtures.py`.
- `ADAPTERS["odp"]` likewise (D412), and four odp cases: three written by LibreOffice (converted from the pptx
  fixtures), one made by `_build_fixtures.py` for a group, a line, notes, a transition and an animation.
- `ADAPTERS["ods"]` likewise (D413), and four ods cases: three written by LibreOffice (converted from the xlsx
  fixtures: cells and a formula, a chart, a picture), one made by `_build_fixtures.py` for repeated rows, a merged
  title, a comment, a date, a union formula, an error cell, a named range and validations.

## [0.1.0] - 2026-11-10

The first version under the versioning policy. Until now the package had a placeholder version (0.0.1), no
`__version__` and no API snapshot, so its surface could change without anyone noticing; from here on
`tests/api/claudia_test_documents.json` holds it to the rules of `docs/versioning.md`. This entry records the surface
as it stands, not a history of how it got there.

### Added
- `__version__`.
- The three-tier check of one case: `Case`, `Model`, `run_case`, `RunResult` (D218).
- The per-format adapters: `Adapter`, `ADAPTERS`; `load_case` loads a case's `spec.py` safely.
- The catalogue file: `Entry`, `load_catalogue`, `save_catalogue`, `select`, `record_run`.
