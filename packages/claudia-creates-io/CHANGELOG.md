# Changelog of claudia-creates-io

Newest first. The format follows [Keep a Changelog](https://keepachangelog.com/); versions follow the versioning
policy (`docs/versioning.md`). While the major version is 0, a minor version may break the API.

## [Unreleased]

### Added
- Lists in text boxes and numbered slide titles in pptx and odp (E9.22): pptx writes `a:buAutoNum` (counting on from
  box to box with `startAt`) or `a:buChar` and reads them back as one list; a marker PowerPoint cannot number (a trail
  such as 2.1) is reported as `list-look`. odp writes one `text:list` per box, continued across boxes
  (`text:continue-list`), with a list style of the scheme, and reads it back. Patching a kept pptx writes the
  markers that changed; a kept odp whose lists changed is written anew.


## [0.6.0] - 2026-11-15

A turned object lies on the slide by its outline (D1021, D1022).

### Added
- `pptx_import_losses` reports `turn`: an object turned so far that its outline cannot lie on the slide.

### Changed
- An object read from a file is kept on the slide by its outline (D1022): `pptx_to_slides` moves a turned object that
  sticks out back in and reads one too large to turn upright; `odp_to_slides` leaves out (`off-slide-object`) a turned
  object whose outline sticks out.
- The picture code the converters of the text app needed too moved out: `Rasterise` and how a picture of a file
  becomes an image object are in `claudia-core`, the transform and frame helpers of odp in `claudia-odf-io` (D464).
  `claudia_creates_io.Rasterise` is still there.

## [0.5.0] - 2026-11-15

A turned object, a picture, the print setup and the language reach the files (D459, D460, D461).

### Added
- `slides_to_pptx` writes the turn of an object (it never did); `slides_to_odp` writes it as `draw:transform`, and
  `odp_to_slides` reads a plain rotation (also after LibreOffice's `skewX` of nothing); `apply_edits_to_odp` patches
  place, size and turn together. `odp_import_losses` no longer reports `rotated-object` for these.
- Pictures come in from `pptx_to_slides` and `odp_to_slides` as image objects, with their alt text, their turn and
  whether they are decorative (pptx); `apply_edits_to_pptx` and `apply_edits_to_odp` move, resize, turn and describe
  them and leave the picture alone. `pptx_import_losses` / `odp_import_losses` still report a picture the model cannot
  hold as `picture`. Text boxes and shapes of a pptx get their alt text read, and a changed one is patched.
- `slides_to_pptx` writes the print layout and paper (`prnPr`, `notesSz`) and the language (`lang` of the runs);
  `pptx_to_slides` reads both; `apply_edits_to_pptx` patches the print setup. `slides_to_odp` writes the language
  (default style of `styles.xml`), `odp_to_slides` reads it and `apply_edits_to_odp` patches it.
- `pptx_import_losses` reports `look`, `formatting` and `link` of the objects it models.

### Changed
- `pptx_unwritten_changes` reports `print_setup` only for what a pptx has no place for (margins other than the paper's
  own, page numbers) and `language` only for a kept file; `odp_unwritten_changes` no longer reports `language`.
- Objects are numbered over text boxes, shapes and pictures, so the ids of a deck with pictures differ from before.

## [0.4.0] - 2026-11-14

Every format says what it cannot hold or show, and what a patch has no place for (D450, D451), and what the earlier
rounds added.

### Added
- `pptx_import_losses` (pictures, tables, charts, groups, other shapes, transitions, animations, notes too long for the
  model) and `pptx_unwritten_changes` / `odp_unwritten_changes`: `planned-time` and the print setup and language, which
  the converters do not write yet.
- `slides_to_pptx` writes an object's description as the shape's alt text (`descr`) and marks a decorative object the way
  PowerPoint 2019 and later do (`adec:decorative` in the shape's extension list, with an empty `descr`: python-pptx would
  otherwise name a picture's alt text after its file).
- `slides_to_odp` writes a description as `svg:desc`; a decorative picture has no text alternative. `odp_export_losses`
  reports `"decorative"` (with how many): ODF 1.3 has no attribute for it.
- Speaker notes (D342, D347) in both formats, in one shared converter (`claudia_creates_io._notes`): Markdown with
  bold, italic and lists (bullets as "• " lines, two spaces a level) to and from the runs of a notes page. PPTX: the
  notes slide, also where another program put the notes in a plain text box; ODP: `presentation:notes` with its notes
  frame. `apply_edits_to_pptx` and `apply_edits_to_odp` patch notes in an existing file in place and leave what they
  do not own untouched; notes that cannot be read back (too long, or a shape the converter does not know) make the
  edit `UnsupportedEdit` rather than lose them.
- Losses: `notes-<feature>` for what the Markdown subset flattens (links, images, code, quotes), `("notes",
  "too-long")` for notes over `MAX_NOTES_LENGTH` on import, and `planned-time` on ODP export (the number of slides that
  had a planned time, which neither format has a place for, D343).

### Changed
- `pptx_export_losses` says `authorship` and `notes-link`, `notes-image`, `notes-code`, `notes-quote` too, as
  `odp_export_losses` did; both include what is not written.
- `pptx_to_slides` gives an imported text box's box the `plain-box` style; its words stay `body-text` (D310).
- `pptx_to_slides` gives an imported autoshape's words the `shape-label` style; the shape itself keeps
  `plain-shape` (D310).
- `odp_to_slides` likewise: an imported text box's box is `plain-box` and its words `body-text`, an imported shape's
  outline `plain-shape` and its words `shape-label` (D310).

## [0.3.0] - 2026-11-13

### Added
- `Rasterise`: a function that draws an SVG as a PNG of a given size.
- `slides_to_odp(..., rasterise=...)` and `slides_to_pptx(..., rasterise=...)`: a rendered text container is written
  as a picture; with a rasteriser as a PNG every program draws (D394).
- `pptx_export_losses`, and `odp_export_losses(..., rasterised=...)`: `rendering-pending`, `svg-picture` and
  `svg-fallback`.

### Changed
- A pptx with an SVG picture no longer fails: it gets an svgBlip with a blank PNG as the fallback.

## [0.2.0] - 2026-11-11

OpenDocument presentations, with maximum preservation from the start (D401, D412).

### Added
- `slides_to_odp`: a model as an odp file (28 by 15.75 cm slides; text boxes, circles, rectangles and triangles with
  their words and the look the model gives them); the title, creator and dates come from a `DocumentInfo` (D411).
- `odp_to_slides`: the pages of an odp as slides and the text boxes and the three shapes on them as objects, in slide
  units, also the ones LibreOffice writes for PowerPoint's (`ooxml-rect`, `ooxml-ellipse`, `ooxml-triangle`, an unfilled
  rectangle with words as a text box). `odp_import_losses` lists what the model does not show (pictures, tables,
  groups, lines, other outlines, notes, transitions, animations, look, formatting...).
- `apply_edits_to_odp`: edit-and-reexport that patches the original bytes: a moved object changes its start tag only,
  texts are edited in place, objects and slides added and removed, a changed look gets a style of its own; everything
  else, in `content.xml` and in every other part, is byte for byte the original's. Raises `UnsupportedEdit` for a
  changed kind or outline, slides in another order and a baseline that is not the file's.
- `odp_export_losses`: what `slides_to_odp` cannot hold (who wrote which words, ...).

### Changed
- The look-reading both converters need is shared in the package (internal); pptx output is unchanged.
- New dependency: `claudia-odf-io`.

## [0.1.0] - 2026-11-10

The first version under the versioning policy. Until now the package had a placeholder version (0.0.1), no
`__version__` and no API snapshot, so its surface could change without anyone noticing; from here on
`tests/api/claudia_creates_io.json` holds it to the rules of `docs/versioning.md`. This entry records the surface as
it stands, not a history of how it got there.

### Added
- `__version__`.
- `slides_to_pptx`, `pptx_to_slides`, and `apply_edits_to_pptx` (D219), which raises `UnsupportedEdit` for what it
  cannot patch.
- `add_transition`: a slide transition, written into the slide part's XML (D147).
