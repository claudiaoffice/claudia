# Changelog of claudia-creates

Newest first. The format follows [Keep a Changelog](https://keepachangelog.com/); versions follow the versioning
policy (`docs/versioning.md`). While the major version is 0, a minor version may break the API.

## [Unreleased]

### Changed
- The typing of an object's words (`insert_text`, `remove_text`, `text_regions`, `text_moved`) is the core's
  `ObjectModel`'s now (CODE-83); `SlideModel` answers the same.
- **Breaking** — the slide is claudia-core's (E6.31, D1470): `SLIDE_WIDTH`, `SLIDE_HEIGHT` and `SlideAnchor` come from
  `claudia_core.slides` (still re-exported here); `SlideModel.slide_names` and `SlideModel.slide_descriptions` are
  replaced by `SlideModel.slides` (`claudia_core.Slides`, the records), and the order of the presentation, which
  `SlideModel.slides` was, is `SlideModel.order`. The state (schema 18) stores the slides as records in that order; an
  older state is not read.
- **Breaking** — the glossary's holder (D1430, see `claudia-core`): `SlideAnchor.holder` (was `container`),
  `SlideModel.holders()`; an anchor's data says `holder`.
- **Breaking** — `DefineImage`, `ForgetImage`, `DefineShape`, `ForgetShape`, `ImagesChanged` and `ShapesChanged` are
  no longer re-exported: claudia-core's `DefineAsset`, `ForgetAsset` and `AssetsChanged` replace them (D1431).
- An object body has one `ref` instead of a field per kind (see `claudia-core`); state schema 16.

### Added
- The refusals a person can meet are `Refusal`s (CODE-78, D1510); `SlideModel.name_taken` adds slides.
  `PrintSetupError` is a refusal.
- `SlideModel.room_for_new_object`: what is left of the slide to the right of a new object's anchor (D1332).
- `requirements()` of a presentation: the fonts its styles ask for by name (`Requirements.fonts`), for the font report a
  server makes when it is opened (E1.9, D1306).
- A slide can be described (E1.13, D1317, D1318): `SlideModel.slide_descriptions`, `thing_description`, `set_thing_description`; `AddSlide.description` brings it back when the removal of a slide is undone. State schema 17: `descriptions` is new (absent: none).
- `SlideModel.restyle_users(old, new)` (from `ObjectModel`): the objects that have a style, as commands that put them
  under another (the deletion of a style, E1.10, D226). Its built-in styles have `origin == "builtin"`.

## [0.20.0] - 2026-11-17

References in text boxes (step H).

### Added
- `SlideModel.fields_of` and `put_fields`: the presentation is a `claudia_core.FieldHost`; a reference to a slide title
  can show its slide number.

### Changed
- **Breaking:** `insert_text` and `remove_text` follow `claudia_core.TypingHost` (with fields).

## [0.19.0] - 2026-11-17

Typing into text boxes (step G).

### Added
- `SlideModel.insert_text`, `remove_text`, `text_regions` and `text_moved`: the presentation is a
  `claudia_core.TypingHost`, so the words of an object are typed into character by character.

## [0.18.0] - 2026-11-17

Agendas (step E, E9.31). State schema 14 → 15 (the words of an object may have `generated`; a snapshot of 14 restores
unchanged).

### Added
- `SlideModel.generated_of` and `put_generated`: the presentation is a `claudia_core.GeneratedHost`; an agenda is a text
  box whose words are generated from the slide titles.

## [0.17.0] - 2026-11-16

Lists in text boxes and numbered slide titles (step D, E9.22). State schema 13 → 14 (a snapshot of 13 restores with
the built-in schemes).

### Added
- `SlideModel.schemes` (a `claudia_core.SchemeBook`, in the state as `schemes`); `item_of`, `put_item` and
  `item_regions`: the words of a text box or shape become a list item with `claudia_core.SetListItem`, and the list
  runs on from box to box across the slides. Numbering the style `slide-title` numbers every slide title.

## [0.16.0] - 2026-11-16

Lists in a presentation, counted with the structure every app shares (step C, E10.21). State schema 12 → 13 (a
snapshot of 12 is rebuilt from the log, D15; restoring one without lists gives none).

### Added
- `SlideModel.lists` (a `ListBook`, in the state as `lists`), `list_in_use`, `labels()`, `reading_order()`,
  `structure_version`, `structure` and `settle`: the presentation is a `ParagraphHost`. The words of the objects are read
  slide by slide, on each slide in stacking order (bottom first), with the slide's number as their place, so a list
  continues from one text box to the next, across slides.

## [0.15.0] - 2026-11-16

A slide title (E9.22, E10.21). State schema 11 → 12 (a snapshot of 11 is rebuilt from the log, D15).

### Added
- The built-in paragraph style `slide-title` ("Slide title"), heading level 1: what names a slide.
## [0.14.0] - 2026-11-16

### Added
- `blank(parts)` on the model (D723): an imported document is redacted in full or in parts — slides (with their speaker notes and every object on them) and objects.

## [0.13.0] - 2026-11-15

Turning objects (rotation-ui).

### Changed
- **Breaking** (what a slide accepts): an object must keep its *outline*, not its frame, on the slide. An upright object
  is judged exactly as before; a turned one by the rectangle that the turn makes of its frame (`claudia_core.turned_extent`),
  so the anchor of a turned object may lie outside the slide while the object does not. `SlideModel.check_anchor` says so.

### Added
- `SlideModel.turned_anchor(obj, rotation)`: the nearest place at which the turned outline is on the slide, or a
  `ValueError` ("too large to turn") when there is none. `turn_command` (the kernel's) carries it in the turn.

## [0.12.0] - 2026-11-15

Names of things (D550).

### Added
- Slides have names, in one namespace with the objects: `AddSlide(name=)`, `SlideModel.slide_names`, and the model's
  `named_things`, `unnamed_things`, `thing_name`, `set_thing_name`; `RenameThing` renames a slide.

### Changed
- State schema 10 → 11 (`names`); older documents have unnamed slides. `RemoveSlide`'s inverse gives the name back.

## [0.11.0] - 2026-11-14

Search and replace (E10.19).

### Added
- The Help topic `creates.searching-and-replacing`, in English and German (E10.19).
- `claudia_creates.search` (not in `__all__`; the server's): the texts of a presentation for a search (`text` boxes,
  shape `label`s, speaker `notes`, `description`s), the scope one slide or all, the part `word`, and
  `plan_replacement` and `replace_command`: object texts keep the authors of what stays, notes are stored whole.
  Depends on `claudia-search`.

## [0.10.0] - 2026-11-14

### Added
- Rendered text containers on slides (D390): `rendered` among the object kinds, definitions and their commands in
  the model, `state_schema` 10 (9 on the `containers` branch; renumbered at the merge, after the speaker notes).

## [0.9.0] - 2026-11-13

Describing objects (BITV 1.1.1), speaker notes and planned times (E10.2, D342, D343). State schema 7 → 8 → 9.

### Added
- `DescribeObject` is exported (it is the kernel's, `claudia_core.DescribeObject`).
- `SetSlideNotes(slide, notes)` (summary "edited the speaker notes of …"): the Markdown notes of a slide, at most
  `MAX_NOTES_LENGTH` characters, `""` clears them; one step with its exact inverse; event
  `{type: "slide_notes", slide, notes}` (`SlideNotesChanged`).
- `SetSlideTime(slide, seconds)` (summary "planned 2:00 for a slide"): the planned time in whole seconds, 1 to
  `MAX_SLIDE_SECONDS` (86 400), `None` clears it; one step with its exact inverse; event
  `{type: "slide_time", slide, seconds}` (`SlideTimeChanged`).
- `SlideModel.notes_of(slide)` and `time_of(slide)`; both are in the state and in the history, so they undo, redo and
  come back from a checkpoint like anything else.

### Changed
- Object bodies carry `description` and `decorative`; see the core changelog. A snapshot written before is retired and
  rebuilt from the log (schema 8).
- State schema 9: `notes` and `times` per slide. An older document opens with none.
- Removing a slide removes its notes and time, and undoing the removal brings them back.

### Added (UX-33)
- `SlideModel.setup_commands`: a new presentation starts in the language of its maker's interface (D915, D917), set by the server as nobody's undo step (UX-33).

## [0.8.0] - 2026-11-13

How a presentation prints, and its language (D917).

### Added
- `PrintSetup(layout, page)` (`claudia_creates.printing`): `layout` is one of `LAYOUTS` — `slides`, `handouts-2`,
  `handouts-3` (with lines for notes), `handouts-4`, `handouts-6`, `handouts-9` — and `page` a `claudia_core.PageSetup`;
  the default is one slide to a page of the slide's size, landscape, without margins. `PrintSetupError` for a layout
  that does not exist; `describe()` reads "6 slides a page on A4, portrait".
- `SetPrintSetup(setup)` (summary "set printing to …"), one step with its exact inverse, event
  `{type: "print_setup", setup}` (`PrintSetupChanged`).
- `SlideModel.print_setup` and `SlideModel.language` (`claudia_core.SetLanguage`, re-exported here); state schema 7.
  Older presentations get the default print setup and no language.

## [0.7.0] - 2026-11-10

The styling-suite plan, steps 1.2 to 1.6.

### Added
- The built-in **`plain-box`**, a `box` style without properties: the box of a text box on a slide (D310).

## [0.6.0] - 2026-11-10

Every built-in style has a kind (D305, D312), and a shape's outline and its words are two styles (D310).

### Changed
- **Breaking:** `plain-shape` is an `outline` style that holds only `fill`, `stroke` and `stroke-width`, and is no
  longer based on Body text (a style and its parent are of the same kind). Its words' look (`36px`, `1.25`,
  centred) moved to the new built-in **`shape-label`**, a paragraph style based on Body text; together the two look
  exactly as the one did. `plain-image` is a `box` style, also a root.

## [0.5.0] - 2026-11-08

The presentation carries its own colour palette (D200, D201).

### Added
- `SlideModel.palette` (a `claudia_core.Palette`), serialized with the document and restored with it, so a
  presentation looks the same on whichever server it is opened. `SlideModel(styles, palette)` takes it.

### Changed
- **Breaking:** `state_schema` is 6. An older snapshot is not read.
- Every built-in style now names colour roles instead of literal colours: `Body text` is `color: @text`, and
  `Plain shape` is `fill: @accent/14`, `stroke: @accent`. The colours are the suite's own, so what the styles look
  like did not change — only what they mean, and the fact that replacing the palette recolours them.

## [0.4.0] - 2026-11-08

The shared object layer (D177–D181), recorded after the fact for the same reason as `claudia-core` 0.9.0.

### Changed
- **Breaking:** `SlideObject` is `VisualObject[SlideAnchor]` — a shared body and a slide anchor — and the object
  commands moved to `claudia_core` as `core.*`. `SlideModel` inherits `ObjectModel[SlideAnchor]`, holds a real
  `StyleBook` (creates' own `Style` dataclass is gone, and its built-in styles are validated like any other), and
  `state_schema` is 5.
- **Breaking:** `claudia_creates.shapes` keeps the disk half only (`ShapeLibrary`, `BUILTIN_DIRECTORY`); the shape
  format itself moved to `claudia_core.shapes`.

## [0.3.0] - 2026-11-07

The grid, and snapping to it (E10.15): a view-only helper, never part of the slide, that each object may follow.

### Added
- `SlideObject.snap` (`bool`, default `True`): whether this object holds to the grid. Unlike the grid itself, this
  is real document state, changed with its own history entry.
- Command `SetSnap(id, snap)`: holds or releases one object; its label swaps between "Snap to grid" and "Release
  from grid" depending on the value it sets. Moving, resizing or editing an object's text never affects its own
  snap, and the reverse: `SetSnap` never conflicts with a colleague's move, resize or text edit of the same object.
- `SlideModel.state_schema` is 4 (a cached snapshot older than this is rebuilt from the log, not upcasted).

### Changed
- **Breaking:** `AddObject.schema` is 3; an upcaster fills schema-2 stored objects' missing `snap` with `True`
  (what every such object already behaved as, there being no way yet to tell it not to).

## [0.2.0] - 2026-11-07

Images on a slide (E10.8): a `kind="image"` object, built on `claudia_core`'s shared `ImageAsset`/`ImageImport`.
Importing from the clipboard and drag-and-drop are deliberately not part of this change; only the server's own
`add_image` method (picking a file) is served so far.

### Added
- `OBJECT_KINDS` now includes `"image"`. `SlideObject` gets two new fields: `image` (an `ImageAsset.id`) and
  `imported` (an `ImageImport`); both are `None` for a text box or a shape. An image object keeps the asset's own
  proportions, exactly as a shape with an `aspect` does.
- `SlideModel.images`: the image assets this document has taken in, mirroring `shapes`. `define_image`/
  `forget_image`/`users_of_image` mirror the shape equivalents; `SlideModel.state_schema` is 3.
- Commands `DefineImage`/`ForgetImage`, mirroring `DefineShape`/`ForgetShape`.
- A built-in style, `plain-image` (no CSS properties: the picture supplies its own look).
- `SlideObject.to_data_for(viewer)` and `ObjectsChanged.to_data_for(viewer)`: like `to_data()`, but an image's
  `imported.source_path` is masked for anyone but the person who imported it (`imported_by`, and that it came from
  disk at all, are not masked).
- State event `image` (`ImagesChanged`), mirroring `shape`.

### Changed
- `SlideModel.serialize()` adds an `"images"` list, sorted by id, between `"shapes"` and `"objects"`.
- **Breaking:** `AddObject.schema` is 2; an upcaster fills schema-1 stored objects' `image`/`imported` with `None`.

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
