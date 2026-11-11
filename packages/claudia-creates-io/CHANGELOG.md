# Changelog of claudia-creates-io

Newest first. The format follows [Keep a Changelog](https://keepachangelog.com/); versions follow the versioning
policy (`docs/versioning.md`). While the major version is 0, a minor version may break the API.

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
