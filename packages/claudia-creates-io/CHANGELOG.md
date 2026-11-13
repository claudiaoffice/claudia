# Changelog of claudia-creates-io

Newest first. The format follows [Keep a Changelog](https://keepachangelog.com/); versions follow the versioning
policy (`docs/versioning.md`). While the major version is 0, a minor version may break the API.

## [Unreleased]

### Added
- `slides_to_pptx` writes an object's description as the shape's alt text (`descr`) and marks a decorative object the way
  PowerPoint 2019 and later do (`adec:decorative` in the shape's extension list, with an empty `descr`: python-pptx would
  otherwise name a picture's alt text after its file).
- `slides_to_odp` writes a description as `svg:desc`; a decorative picture has no text alternative. `odp_export_losses`
  reports `"decorative"` (with how many): ODF 1.3 has no attribute for it.

### Changed
- `pptx_to_slides` gives an imported text box's box the `plain-box` style; its words stay `body-text` (D310).
- `pptx_to_slides` gives an imported autoshape's words the `shape-label` style; the shape itself keeps
  `plain-shape` (D310).
- `odp_to_slides` likewise: an imported text box's box is `plain-box` and its words `body-text`, an imported shape's
  outline `plain-shape` and its words `shape-label` (D310).

## [0.3.0] - 2026-11-13

### Added
- `Rasterise`: a function that draws an SVG as a PNG of a given size.
- `slides_to_odp(..., rasterise=...)` and `slides_to_pptx(..., rasterise=...)`: a rendered text container is written
  as a picture; with a rasteriser as a PNG every program draws (D344).
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
