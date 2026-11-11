# Changelog of claudia-composes-io

Newest first. The format follows [Keep a Changelog](https://keepachangelog.com/); versions follow the versioning
policy (`docs/versioning.md`). While the major version is 0, a minor version may break the API.

## [0.2.0] - 2026-11-11

OpenDocument text, with maximum preservation from the start (D401, D402).

### Added
- `text_to_odt`: a model as an odt file, built-in styles as the styles of the same name, open suggestions as native
  tracked changes. A change is dated with when it was made (`change_times`, by suggestion id) or, with no time, the
  placeholder LibreOffice needs: 1970-01-01. With an `info` (a `DocumentInfo`) the file's `meta.xml` says who made it
  and when it was last changed (D411).
- `export_info(log, branch)`: the dates and people of a document, and when each suggestion was made, read from its
  command log for the converters (D411).
- `odt_to_text`: the paragraphs of an odt as a model, also those in lists and sections; styles map by name, and a style
  based on a known one is that one. `odt_import_losses` lists what the model does not show (tables, frames, notes,
  formatting, links, lists, tracked changes...).
- `apply_edits_to_odt`: edit-and-reexport that patches the original bytes: text edited in place (links, bookmarks and
  notes stay), blocks added, removed and restyled, suggestions as tracked changes; everything else, in `content.xml`
  and in every other part, is byte for byte the original's. Raises `UnsupportedEdit` for a moved block or a baseline
  that is not the file's.
- `odt_export_losses`: what `text_to_odt` cannot hold (a style that is written as body text, authorship of runs,
  remarks, suggestions it cannot place).

### Changed
- `text_to_docx` takes `change_times` and dates its tracked changes with them (`w:date`); one with no time is written
  without a date, as before.
- `apply_edits_to_odt` takes `info` and keeps the file's `meta.xml` true: modified by whom and when, the edit counted,
  Claudia as the generator, all else in it as it was. An unchanged file is still the same bytes.
- `UnsupportedEdit` is also what `apply_edits_to_odt` raises. docx and odt share the choice of which open suggestions
  are written as tracked changes (internal).

## [0.1.0] - 2026-11-10

The first version under the versioning policy. Until now the package had a placeholder version (0.0.1), no
`__version__` and no API snapshot, so its surface could change without anyone noticing; from here on
`tests/api/claudia_composes_io.json` holds it to the rules of `docs/versioning.md`. This entry records the surface as
it stands, not a history of how it got there.

### Added
- `__version__`.
- `text_to_docx` (tracked changes included, D147), `docx_to_text`, and `apply_edits_to_docx`, which patches only what
  changed onto the original bytes (D217) and raises `UnsupportedEdit` for what it cannot.
