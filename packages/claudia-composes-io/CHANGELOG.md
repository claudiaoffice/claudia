# Changelog of claudia-composes-io

Newest first. The format follows [Keep a Changelog](https://keepachangelog.com/); versions follow the versioning
policy (`docs/versioning.md`). While the major version is 0, a minor version may break the API.

## [Unreleased]

## [0.4.0] - 2026-11-15

Lists, the page, the language, the styles and the palette reach odt and docx, and a kept docx can have paragraphs added
and removed (D453–D456).

### Added
- Lists in odt and docx: items are written as list items (`text:list`, `w:numPr`) with the scheme, start and name of
  their list; they are read back as the same items and lists, and `apply_edits_to_odt` / `apply_edits_to_docx` keep
  and change the lists of a kept file. `"lists"` is no longer a `not-written` loss.

- The page (paper, orientation, margins, page numbers) and the language of a text in odt and docx: written, read
  back and changed in a kept file (D454). `"page"` and `"language"` are no longer `not-written` losses.
- The paragraph styles of a text in odt and docx: every style is written with its look, its palette colours and its
  parent; a kept file gets the styles that changed, and a style a paragraph now has (D455). `"styles"` and
  `"palette"` are no longer `not-written` losses. A property a file cannot say is a `style-property` loss.

- `apply_edits_to_docx` adds and removes paragraphs in a kept file: a new block is a new paragraph after the paragraph
  of the block before it, a removed block takes its paragraph with it (a paragraph that ends a section of the file is
  only emptied), and what the file loses with it is named in the new `losses` argument (`removed-frame`,
  `removed-footnote`, `removed-endnote`, `removed-comment`, `removed-link`, `removed-tracked-change`; `style` for a
  block whose style the text lacks), as for `apply_edits_to_odt` (D456). Tables, pictures and the rest of the file stay.

### Changed
- `apply_edits_to_docx` keeps the runs of a paragraph that hold a picture, the mark of a note or a field when the words
  of the paragraph are written again; it used to take them out with the words (D456).
- `apply_edits_to_docx` no longer raises `UnsupportedEdit` for an added or removed paragraph: it raises it for blocks
  moved relative to each other and for a baseline that is not what the file holds. The server's docx download of an
  imported file stays a patch of that file (`patched: true`) instead of becoming a new file with a `not-patched` loss.
- `odt_export_losses` and `docx_export_losses` no longer report a style of the model as `style`: only a style id the
  model does not have.
- `odt_import_losses` and `docx_import_losses` report `list-look` (a list drawn otherwise than the model draws it)
  and `list-depth` instead of `list`.
- `apply_edits_to_docx` keeps the Word style of a paragraph whose style did not change.

## [0.3.0] - 2026-11-14

Every format says what it cannot hold or show, and what a patch has no place for (D450, D451).

### Added
- `docx_import_losses` (tables, lists, frames, notes, comments, formatting, links, tracked changes, styles the model
  does not have) and `docx_export_losses` (styles written as Normal, authorship, remarks, suggestions, and what is not
  written yet).
- `odt_unwritten_changes` and `docx_unwritten_changes`: what changed in a text (against the baseline of an
  edit-and-reexport, or an empty text for a new file) that the converter does not write yet: page setup, language,
  lists, palette, style definitions, floating objects. `odt_export_losses` includes them for a new file.

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
