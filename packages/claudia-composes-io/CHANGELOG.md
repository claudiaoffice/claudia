# Changelog of claudia-composes-io

Newest first. The format follows [Keep a Changelog](https://keepachangelog.com/); versions follow the versioning
policy (`docs/versioning.md`). While the major version is 0, a minor version may break the API.

## [Unreleased]

### Added
- Names and descriptions in docx and odt (E1.13, D1311, D1318): **`Annotations`** (`names`, `comments`, `author`,
  `when`) is the new `annotations=` argument of `text_to_docx` and `text_to_odt`. A paragraph with a name in
  `names` gets a bookmark around its words (a docx cannot hold a space in a bookmark, so a space is written as `_`);
  one with a text in `comments` gets a review comment by `author` at `when` (`add_comment` in a docx,
  `office:annotation` in an odt). Without it nothing changes. `docx_to_text` and `odt_to_text` read a bookmark around
  the words of exactly one paragraph as that paragraph's name (not one a program makes for itself, starting with `_` or
  `ref-`; a clash gets `(2)`; a heading keeps its title); comments are not read back as descriptions.

### Changed
- The docx and odt exports leave the box properties of the table looks out of the style-by-style check
  (`TABLE_STYLE_IDS`), and the paragraph styles of the table roles are written **without** their lines, fill and
  padding: a table writes them as the properties of its cells (E9.32, D1214). Objects are built with `ref=` (see
  `claudia-core`).
- `docx_import_losses` and `odt_import_losses` count as `table` only the tables the text does not hold (nested ones
  included); a regular table is an own table now. `docx_export_losses` and `odt_export_losses` have no `table` loss and
  `docx_unwritten_changes`/`odt_unwritten_changes` no `tables` facet: tables are written.
- `apply_edits_to_odt` raises `UnsupportedEdit` for a text whose tables changed (the file is written anew);
  unchanged tables stay in the file as they are.

### Added
- Tables in docx and odt (E9.32, D1214): a regular table (1–100 rows, 1–10 columns, a rectangular grid, cells of one
  paragraph of plain words, merges that make rectangles, a place after a paragraph of the flow) is read as an own table
  with its header rows, number columns, column widths, table width and merges; every other table stays in the file and
  is counted as the loss `table`. The tables of the text are written as real tables (`w:tbl` with `w:gridSpan`,
  `w:vMerge`, `w:tblHeader`; `table:table` with spans, covered cells and `table:table-header-rows`), the look on the
  cells, numbers aligned right, the total row as words. `apply_edits_to_docx` replaces, removes and adds the tables
  that changed in place.
- References in docx and odt (step H): a docx gets a bookmark at each target and Word's `REF`/`PAGEREF` field for each
  reference, an odt a `text:bookmark` and a `text:bookmark-ref`, each with what it reads as now; both are read back as
  references to the same paragraphs (one whose bookmark starts no paragraph comes in as its words). A kept file with a
  reference is written anew.
- Tables of contents in docx and odt (E9.31): docx writes a TOC field in a content control with its entries and asks
  Word to update the fields on opening; odt writes `text:table-of-content` with its entries, and lists the loss
  `toc-pages` (the entries carry no page numbers). Both read a table back with its levels. The Contents styles are
  Word's TOC Heading and toc 1 to 9, OpenDocument's Contents Heading and Contents 1 to 9. A kept file with a table of
  contents is written afresh (`UnsupportedEdit`).
- Numbering schemes and numbered headings in docx and odt (E9.22): a list is written with the levels of its scheme
  (Word's number format and level text, OpenDocument's list style), and read back with the document's scheme that draws
  it, or a new one; only a level the model cannot say is still reported as `list-look`. A numbered heading style is a
  Word style with `w:numPr` (read back as the style's numbering, not as items) and the odt's `text:outline-style`.
  `apply_edits_to_docx` and `apply_edits_to_odt` write a changed scheme or heading numbering into the kept file.


### Changed
- Headings by their level (E9.22): every paragraph style with a heading level of 1 or deeper is a heading in the file
  (`text:h` with its `text:outline-level`, the style's `default-outline-level`; Word's `w:outlineLvl`, from 0), and keeps
  with the next paragraph; Heading 3 to 6 come and go as the files' own Heading 3 to 6. A heading deeper than the text
  has a style for (an `outline-level` of 7 and more) is body text and reported as before. Word's names of the built-in
  styles are kept in one table (`WORD_NAMES`), not two.
### Fixed
- Everything in a file that anybody may have written is read through `claudia_opc_io.parse_xml` (no entity is expanded, none fetched) and unpacked only after `claudia_opc_io.check_package` has judged its size (SEC-15); the odt reader's styles and content parts, which were read with lxml's defaults, now use it.
- `docx_to_text` and `odt_to_text` read the fonts of the file (E3.13, bug 1): Body text, Title, the headings and Quote
  take the font their style names in the file -- a docx's own font or theme font (`minorHAnsi`), along `basedOn` and
  the document defaults; an odt's `style:font-name` or `fo:font-family`, along the parent styles and the default
  style. The font is the one the file names (Arial), never a stand-in; a fresh export writes it back, and it is no
  loss.
- A style whose font is a generic family is written into docx and odt as the font Claudia shows it with (`serif` as
  Fraunces, `system-ui` as Inter, `ui-monospace` as JetBrains Mono), not as Liberation Serif, Sans or Mono, the next
  family of the list, or a font called `ui-monospace` (CODE-42; `claudia_core.stand_ins.file_font`).

## [0.7.0] - 2026-11-17

Properties and links of a docx (D466, D468).

### Added
- `text_to_docx(..., info=)`: the file's properties are the log's (title, creator, dates) and not the template's
  (IEW-02).
- `removed-link` loss of a docx patch: an edit removed the words a link covered.

### Fixed
- Editing the words of a docx paragraph that held a hyperlink wrote the words of the link twice (IEW-01). The link is
  carried to the place of its words in the new text (`_docx_links.carry_links`).

## [0.6.0] - 2026-11-15

Text boxes and shapes floating over a text reach docx and odt (D465).

### Added
- `text_to_docx` and `text_to_odt` write the text boxes and the shapes (circle, rectangle, triangle) of a text as
  drawings in the paragraph they hang from, with their words, size, turn, description, fill and outline.
- `docx_to_text` and `odt_to_text` read them back as text box and shape objects (`x1`, `x2`... in the order of the
  file); the look of a box is written but not read, and `docx_import_losses` / `odt_import_losses` report `look` when
  the file's differs from the model's.
- `apply_edits_to_docx` and `apply_edits_to_odt` add, remove, move, resize, turn, reword and describe the boxes of a
  kept file; a box whose kind, shape or style changes is drawn anew (and its foreign look lost); the ones nobody
  touched stay byte for byte. The unwritten-change facets of boxes follow what the writers hold.

### Fixed
- `docx_to_text` counted a Word text box twice (its drawing and the picture Word keeps for old readers) (IEW-21).
- The patch of a docx or odt wrote a style the file already had under a second name (`Shape label 2`) when an object
  was restyled to it (IEW-22).

## [0.5.0] - 2026-11-15

Pictures floating over a text reach docx and odt (D464).

### Added
- `text_to_docx` and `text_to_odt` write the image objects of a text (and a rendered text container) as pictures: a
  drawing in the paragraph they hang from at their character, not wrapping the words, with their description, size
  and turn. An SVG is written with a PNG next to it in a docx (a program that cannot draw an SVG shows that), and as
  the SVG itself in an odt; `rasterise` (new argument) draws a PNG of a rendered container or an SVG.
- `docx_to_text` and `odt_to_text` read the pictures of a file the model can show as it is (an image the app decodes,
  not cropped, in its own proportions, turned by nothing but a rotation; an inline picture of a docx floats in the
  model) as image objects with their alt text and, in a docx, the mark that says they are decoration.
  `docx_import_losses` and `odt_import_losses` report `picture` for those they do not show as they are; `frame`
  stays for what is no picture.
- `apply_edits_to_docx` and `apply_edits_to_odt` (new argument `rasterise`) add, remove, move, resize, turn and
  describe the pictures of a kept file, and keep the ones nobody touched byte for byte. An image that no frame shows
  any more leaves the package of an odt.
- New losses: `decorative` (odt export: ODF 1.3 has no mark for decoration), `svg-fallback` (docx) and `svg-picture`
  (odt) for an SVG no rasteriser drew, `rendering-pending` for a rendered container nothing has been drawn for.
  `docx_export_losses` and `odt_export_losses` take `rasterised`. `"pictures"` is no longer a `not-written` loss.

### Fixed
- `apply_edits_to_odt` wrote the styles of the app's own files again under a second name (`Remark_2`, ...) after any
  edit of a text the app had written itself (IEW-17).

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
