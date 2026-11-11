# OpenDocument: `claudia-odf-io`, and odt import, export and edit-and-reexport (D401–D410)

The first OpenDocument format, on the `openoffice` branch. The aim the owner set: **maximum preservation from day
one** (D403) — an edited file is the file it was, with only the edited elements changed — and a list of what could
not be kept in both directions (D405). docx (D217) restored whole parts; an odt has one `content.xml`, so this had
to be a different mechanism.

## What was built

**`claudia-opc-io` 0.2.0** — `write_parts` writes `mimetype` first and stored, every part with the 1980-01-01 timestamp
(D404). The contents of docx/pptx/xlsx parts are unchanged.

**`claudia-odf-io` 0.1.0** (new, lxml only):

| module | what |
|---|---|
| `names` | `NS`, `qname`, style-name encoding (`Heading_20_1` ⇄ `Heading 1`, `_xx_` escapes) |
| `splice` | `XmlPart`: parse to *find* elements, expat for their byte spans; edits are recorded (replace, remove, insert before/after/into) and spliced into the original bytes. No edits → identical bytes; with edits, everything outside them is identical |
| `paragraph` | `read_text`, `set_text` (edit the characters that differ: token diff refined by common prefix/suffix, in place, so spans/links/bookmarks/notes stay; ODF white-space collapsing handled with `text:s`, `text:tab`, `text:line-break`), `insert_elements` (change marks between characters), `hidden_content` |
| `package` | `new_package` (mimetype, content, styles, meta, extras, manifest), `problems` (zip rules, manifest agreement, well-formed XML, `office:version`), `read_manifest` |
| `report` | `Loss`, `LossLog` |

**`claudia-composes-io` 0.2.0** — `text_to_odt`, `odt_to_text`, `apply_edits_to_odt` (a `_Patch` object: remove, edit,
add; tracked changes; styles added to `styles.xml` when missing), `odt_import_losses`, `odt_export_losses`.

**Server** — `export_office` takes `"odt"` for the text app; the answer has `losses` (only for formats that can say).
**Web** — "OpenDocument text (.odt)" in File ▸ Export…; `ExportedFile` type.
**CI** — job `odf-libreoffice` (non-blocking) running `scripts/odf_libreoffice_check.py`.
**Test documents** — `ADAPTERS["odt"]` and six cases: `heading-styles`, `beyond-claudia/table`, `beyond-claudia/image`
(the three written by LibreOffice 24.2.7, converted from the docx fixtures and checked in; their output carries
timestamps, so `_build_fixtures.py` cannot make them again), `rich-paragraph`, `tracked-change-suggestion`,
`lists-and-sections` (made by `_build_fixtures.py`, deterministic).

## Things worth knowing

* **lxml, not odfdo** (D401): the call was made while implementing; only `splice.py` and `paragraph.py` would change.
* **A real bug found on the way**, in the span finder: expat reports the end of an *empty* element at the next token, so
  an empty element directly before its parent's end tag (`<text:p/></text:list-item>`) was given the parent's end tag.
  Found by a test for `insert_into` on a self-closing element; fixed by deciding emptiness from the start tag (`/>`),
  with a regression test.
* **Tracked changes need a date** (D406): LibreOffice reads a change without `dc:date` as nothing at all. The
  placeholder is 1970-01-01T00:00:00, the one LibreOffice writes itself.
* **A block added after a list item** is a paragraph inside that item (D402): the model has no bullets. Adding before a
  list, or after the list's *paragraph in the flow*, leaves the list byte-identical (`lists-and-sections`).
* **`TextModel()` always has one empty block**, so a text with no paragraph reads as a model with one; `_Patch` treats it
  as "nothing to patch, nothing to add while empty".
* **Every export of typed text reports `authorship`** (D405): true, and the screen may show it quietly.
* **Duplicate test module names** (`test_package.py` in two packages) break collection of the whole suite: odf-io's is
  `test_odf_package.py`.

## How it was checked

Unit tests (odf-io 126, composes-io 82 with 150 random edits of a rich file, server export tests, 545 web tests, six
library cases) and against LibreOffice 24.2.7 (D409; `scripts/odf_libreoffice_check.py`, 13 of 13 files read, and by hand through txt and docx conversion): the from-model export (all five styles, spaces, tabs,
line break, a tracked change) read as `w:del`/`w:ins`, `Title`/`Heading1`/`Heading2`/`BlockQuotation` in docx; edits
(text, two blocks added) of the three LibreOffice-written fixtures converted to txt and docx, with the table
(`w:tbl`) and the picture (`w:drawing`, media part) intact. Gate: ruff, format, mypy, vulture, i18n catalogue, API
snapshots, decision log, coverage floors.

## Open

* The loss-list screen (SVG first), the import screen (another agent), Save As .odt of an edited import in the app
  (the app does not keep the original bytes), styles beyond names (D407), odp (E10.3) and ods (E6.9, formulas D408).
* Making the LibreOffice job blocking once it has a track record, and schema validation (D409). The OASIS schema was unreachable from the sandbox.
* `meta.xml` is not touched by an edit (the file does not say Claudia edited it); a decision for later whether it should.
* Whether `export_office` should offer tracked changes for odt (D212 says no for docx; the converter can).
