# Changelog of claudia-creates

Newest first. The format follows [Keep a Changelog](https://keepachangelog.com/); versions follow the versioning
policy (`docs/versioning.md`). While the major version is 0, a minor version may break the API.

## [0.1.0] - 2026-11-03

First real model of the presentation app (E10.1): slides holding text boxes and shapes. Until now the package was a
stub that no server served, so no document of the old shape can exist.

### Added
- Shape library: `ShapeLibrary.load(directories)` reads the shapes that ship with claudia (`rectangle`, `circle`,
  `triangle`) and any folder of `<id>.json` files. A shape is plain JSON (format 1): an outline of absolute `M`, `L`,
  `C`, `A`, `Z` commands in a 100 by 100 box, an optional `aspect` (a circle keeps 1) and an optional `text_area`.
  `parse_shape` and `ShapeDefinition.from_data` refuse anything else with a sentence that says where; a file that is not
  right is skipped and listed in `ShapeLibrary.problems`.
- `SlideObject`: a text box or a shape on a slide of 1600 by 900 integer units, with a named style (`BUILTIN_STYLES`:
  `body-text`, `plain-shape`; CSS from the allow-list `ALLOWED_CSS`).
- Commands `AddObject`, `MoveObject`, `ResizeObject`, `SetText`, `RemoveObject`, `DefineShape`, `ForgetShape`. A document
  keeps its own copy of every shape it uses (`DefineShape`), so it opens the same on a server without that shape.
- Collaborative undo (D46): a colleague's later move, resize, text or removal of the same object makes the undo
  refused, never overwritten; moving an object and editing its text are independent.
- `AddSlide` takes a place, so undoing the removal of a slide puts it back where it was.
- A new presentation starts with one empty slide, `s1` (`SlideModel.empty()`); every command has a sentence for the history.
- State events `objects` (changed objects, removed ids, stacking order), `shape` and `slides`.
- `ObjectSet.from_data` validates a selection that comes from a client.

### Changed
- **Breaking:** `PutObject` is gone, replaced by the typed commands above. `SlideModel.state_schema` is 2 and
  `SlideModel.serialize()` lists `slides`, `shapes` and `objects` (in stacking order). `RemoveSlide` still needs an empty slide.
