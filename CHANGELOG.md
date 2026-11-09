# Changelog

All notable changes to the public API of `claudia-core` are listed here, newest first. The format follows
[Keep a Changelog](https://keepachangelog.com/); versions follow the versioning policy (`docs/versioning.md`).
While the major version is 0, a minor version may break the API; every break is marked **Breaking**.

## [0.11.0] - 2026-11-08

A diagram joins the shared object layer as its own kind, so a chart can be a floating object on a slide, sheet
or paragraph the same way an image or a shape is (E6.6). What a diagram draws is deliberately opaque to the
kernel — the same split the object layer already draws between a body and an anchor, applied to a kind's own
content instead of its placement, since only computes (today) knows what a chart's range and titles mean.

### Added
- `claudia_core.objects`: `"diagram"` joins `OBJECT_KINDS`; `ObjectBody` gained a `diagram` field (the id of a
  definition, alongside its existing `shape`/`image`).
- `DiagramDefinition`: a `Protocol` for what a diagram draws, mirroring `Anchor` — an app reads its own back
  through the new `ObjectModel.diagram_from_data(data)` hook, the one door this data enters through.
- `ObjectModel.diagrams`, `define_diagram`, `forget_diagram`, `replace_diagram`, `users_of_diagram`, and
  `diagrams_to_data()`/the `diagrams` parameter of `restore_objects()` — the same shape as the existing
  shape/image methods, except a diagram can also be redefined in place (`replace_diagram`), since unlike a
  shape or an image, a diagram is meant to be edited after the fact.
- `DefineDiagram`, `UpdateDiagram` and `ForgetDiagram`: the commands behind the above, each with its exact
  inverse (mirroring `DefineShape`/`ForgetShape`).
- `DiagramsChanged`: the event a view hears when a diagram definition is added, edited or forgotten.

### Changed
- `AddObject.label`/`summary` and `shifted_by` now cover `"diagram"` alongside `"text"`/`"shape"`/`"image"`.

## [0.10.0] - 2026-11-08

The document's palette: colours named by what they mean (D200–D203). **Breaking:** `StyleBook.views` gained a
parameter and every style now travels with a third form of its CSS; a model that holds a style book is expected to
hold a palette beside it.

### Added
- `claudia_core.palette`: `ColourRole` (id, name, purpose, colour), `Palette` (an ordered, extensible mapping of
  them), `Reading` (how one role reads against another), `PaletteChanged`, and the commands `SetRole` and
  `ReplacePalette`, each with its exact inverse. Plus `builtin_palette()`, `BUILTIN_ROLES` (nine roles), `PAIRINGS`,
  `TEXT_FLOOR`, `UI_FLOOR`, `MAX_ROLES`, `contrast()` and `luminance()` (WCAG 2.2).
- `resolve_css(css, colours)`, `roles_used(css)` and `rgb_of(colour)` in `claudia_core.css`.
- `core.SetObjectStyle`: puts an object under another style of its own. An object's style was settled by
  `AddObject` and could never be changed again, which left a style menu with nothing to do.
- `claudia_core.styles.palette_colours(model)`: the role colours of a model that has a palette, asked of the model
  rather than imported, so that the two modules can still be used apart.

### Changed
- **Breaking:** `CSS_VERSION` is 2. A colour may now be a role of the palette — `@accent`, or `@accent/55` for that
  role at 55% opacity — wherever a colour is accepted, including inside a `border-*` shorthand. `@` is no longer
  refused outright in a value; every value check other than the colour one refuses it anyway, so a role can only
  land where a colour belongs. Nothing else about the allow-list changed: `url()`, `var()`, `calc()` and
  `!important` are still refused, which is what `resolve_css` exists to protect.
- **Breaking:** `StyleBook.views(colours=None)` now returns a `resolved` form of each style beside `computed`.
  `computed` still names the roles, which is what a style menu shows; `resolved` has the literal colours, which is
  what a client draws with. Without `colours`, a declaration naming a role is left out of `resolved`.
- Changing the palette emits `StylesChanged` as well as `PaletteChanged`: a client is deliberately unable to
  resolve a role itself, so the styles have to travel again.

## [0.9.0] - 2026-11-08

One shared object layer for shapes, images and text boxes, and an object's words as a paragraph (D177–D182). This
release was built but never written down; it is recorded here after the fact, with the versioning policy's own
rule in mind — the API changed, so it gets a version and an entry.

### Added
- `claudia_core.objects`: `ObjectBody`, `VisualObject[A]`, the `Anchor` protocol, `ObjectModel[A]`, `ObjectSet`,
  `ObjectsChanged`, `ImagesChanged`, `ShapesChanged`, `paragraph_for()`, and the whole `core.*` object command
  family — `DefineShape`, `ForgetShape`, `DefineImage`, `ForgetImage`, `AddObject`, `RemoveObject`, `MoveObject`,
  `ResizeObject`, `RotateObject`, `SetText`, `SetParagraph`, `SetParagraphStyle`, `SetSnap`.
- `claudia_core.paragraphs`: `Paragraph`, `Run` and the run arithmetic that used to be `claudia_composes.runs`, so
  that one paragraph entity serves a document, a text box and a shape's label alike.
- `claudia_core.shapes`: `ShapeDefinition`, `parse_shape`, `ShapeError`, `FORMAT`, `BOX` — the shape format only;
  reading a library off a disk stays in `claudia_creates`, because the kernel does no I/O.
- PNG among `SUPPORTED_IMAGE_FORMATS`, APNG included, with a still first frame taken without re-encoding.

### Changed
- **Breaking:** an object is a shared body plus a per-app anchor. `ObjectBody.text` became
  `ObjectBody.paragraph: Paragraph | None`, so an object carries two styles: its own (`fill`, `stroke`,
  `stroke-width`) and its paragraph's.
- **Breaking:** `ObjectSet` names a `container`, not a slide or a sheet.

## [0.8.0] - 2026-11-07

I18n groundwork (E5.7, D31, D148): the kernel gains stable error identity, without taking on gettext or any other
translation dependency itself.

### Added
- `KernelError.code` and a unique `code: ClassVar[str]` on every subclass (`unknown_command`, `schema_too_new`,
  `missing_upcaster`, `revision_mismatch`, `region_held`, `stale_edit`, `undo_refused`, `undo_conflict`,
  `redaction_error`, `replay_error`): a machine-readable identity for each error, independent of `str(exc)`'s
  baked English sentence. A future translator picks the message to show from `code`; the kernel itself still does
  not import gettext or know any catalog exists (`test_purity.py`).
- `MissingUpcaster` now also carries `self.kind` and `self.schema` (previously only in the message text).

Note for `scripts/api_surface.py`: it inspects callable signatures and `property` instances only, so a plain
`ClassVar` attribute like `code` does not show up in the snapshot diff on its own — the snapshot still needed
regenerating by hand for this release, same as any other addition.

## [0.7.0] - 2026-11-07

Images, shared by every app that can hold a picture (E10.8). This is the first piece of the image-import feature;
`claudia-creates` builds on it to let the **creates** app put an imported image on a slide. `claudia-composes` and
`claudia-computes` can reuse the same `ImageAsset`/`ImageImport`/`decode_image` for their own object kinds later,
without re-deciding what a decoded image or an import record looks like.

### Added
- `decode_image(data) -> ImageAsset`: a pure-Python, dependency-free decoder for JPEG, GIF, BMP and SVG
  (`SUPPORTED_IMAGE_FORMATS`). It reads only what is needed to find a pixel size — a JPEG's SOF marker, a BMP's
  `BITMAPINFOHEADER`, a GIF's logical screen descriptor and block structure, an SVG's `width`/`height` or `viewBox` —
  and never decodes a pixel. `MAX_IMAGE_BYTES` (8 MB) bounds a single asset.
- `ImageAsset`: a decoded image, identified by the sha256 of its bytes (so two imports of the same picture can share
  one asset once an app chooses to reuse it). For an animated GIF, `animated` is true and `first_frame` holds a
  complete, still GIF of just the first frame, so a view can show something before the person asks to play it.
- `ImageImport`: how one copy of an asset entered one document — `imported_by`, `imported_at`, `alt` (required: every
  imported image needs a short description), `source` (`"disk"` today; `"clipboard"` is a later addition), and
  `source_name`/`source_path`. `ImageImport.masked(viewer)` hides `source_path` from everyone but the importer,
  without hiding that the image came from disk or who imported it (the product decision that a colleague sees
  "imported from disk", not the importer's own filesystem path).
- `ImageError`: raised by `decode_image` and by `ImageAsset.from_data`/`ImageImport.from_data`, naming what is wrong.
- SVG is sanitized, not merely parsed: a `DOCTYPE` or `ENTITY` declaration is rejected outright at the text level
  (an entity-expansion bomb or an external-entity read starts with one, and the standard library's XML parser does
  not guard against either); `<script>`, `<foreignObject>`, `<iframe>`, `<use>` and the SMIL `<animate*>`/`<set>`
  elements are removed; event-handler attributes (`on*`) and any `href`/`xlink:href` that is not a same-document
  anchor (`#...`) are removed. The rest of the drawing survives.

### Fixed
- **`decode_image`'s `MAX_IMAGE_BYTES` cap was enforced on the live-import path only.** `ImageAsset.from_data` — the
  deserialization path used for command-log replay and for loading a document from storage — accepted a payload of
  any size, so a document whose command log already holds an oversized image (however it got there) would decode it
  anyway, including its `first_frame`. Fixed with a cheap pre-check on the base64 text length (so an oversized
  payload is rejected without decoding it) plus an exact check on the decoded length, applied to both `data` and
  `first_frame`.
- **A truncated GIF data sub-block miscounted frames instead of failing.** The block-structure walk did not check
  whether a length byte claimed more data than remained, so it could run past the end of the buffer and return a
  position the caller reads as "no more blocks" — a corrupted first frame of a genuinely animated GIF silently
  decoded as `animated=False` with only that frame, not an error. `ImageError` now, for a sub-block whose length
  runs past the end of the data.
- **The SVG sanitizer's `DOCTYPE`/`ENTITY` check only scanned the first 2048 bytes.** A `DOCTYPE`/`ENTITY`
  declaration pushed past that offset by padding earlier in the prolog (a long comment, say) is still well-formed
  XML and still reached the parser unredacted — an XXE/entity-expansion bypass, not merely an edge case. The check
  now scans the whole decoded text.

### Notes for implementers
- `ImageAsset.to_data()`/`from_data()` carry the image's bytes as base64 text, because a document's state and the
  server's wire protocol are both JSON (there is no binary attachment channel). A document with many or large
  images can approach the protocol's 16 MB message limit on a plain `snapshot` request; that is an accepted
  limitation of embedding images in the document state (there being no separate blob store yet, see the E2
  container format), not something this change solves.
- `ImageImport`'s redaction story is intentionally not addressed here: it is covered by the project's open decision
  on redaction in general, not decided as a side effect of adding images.

## [0.6.0] - 2026-11-06

Go back to a checkpoint, with everybody's consent (E3.7, D149): the live session needs a read-only preview of a line
before anybody is asked to switch to it.

### Added
- `Document.peek_line(line)`: the state of any line (active or hidden), rebuilt on a scratch model, without
  switching to it and without touching the live model, undo steps or checkpoints. `KernelError` for a name that is
  not a line of this document.

## [0.5.0] - 2026-11-03

Styles in the kernel (E1.10, D73, D75): one CSS allow-list and one style model for all three apps.

### Added
- `ALLOWED_CSS`, `CSS_VERSION` (1), `validate_css`, `parse_css`, `format_css`, `CssError`, `CssProblem`: the CSS a style
  may hold. A short list of properties and value types (font, size, weight, style, decoration, colours, alignment,
  line height, spacing, margins, padding, borders (`border-left` and the like: width, style, colour), and `fill`, `stroke`, `stroke-width` for shapes); nothing with `url()`, `var()`,
  `calc()`, `@`-rules or `!important`. `parse_css` reads the text of a style and reports every problem with its line
  and property.
- `StyleDef`, `StyleBook` (styles based on each other; stores only differences; `computed`, `chain`, `children`,
  unique names and ids, provisional names such as `Heading 1 (changed)`) and the event `StylesChanged`.
- Commands `CreateStyle`, `ChangeStyle`, `RenameStyle` and `RemoveStyle` (the undo of a creation). A model that wants
  styles has a `styles` attribute (a `StyleBook`) and may answer `style_in_use(style_id)`. A colleague's later change
  of the same property, a rename, or a style based on the new one makes an undo refused, never an overwrite.

## [0.4.0] - 2026-11-02

### Added
- `Command.summary`: a sentence for the history panel (`B3 = 40`); by default the label. It may name values, so it is
  not part of what survives a redaction. `Batch.summary` joins the first three of its commands.
- The `command` event carries `summary`.

## [0.3.0] - 2026-11-02

### Added
- `Document.execute(..., base=revision)`: an edit made against a view that is not on the active line is refused with
  the new `StaleEdit` (edits in flight during a restore or switch).
- `Document.switch_to(line, author)`: the way back after a restore. `Document.lines()` and `Line` list the lines.
  `Switch` (`core.Switch`) records the switch in the log.
- `CommandLog.on_path(rev, head)`.
- `__version__` and a curated `__all__`; the API surface is snapshotted by a test.

### Changed
- `BranchSwitched.fork_point` is now the last revision both lines share (it was the checkpoint's entry, which is the
  same thing for a restore).

### Removed
- Names that were only importable by accident (`claudia_core.clock` etc. as attributes of `__all__`).

## [0.2.0] - 2026-11-02

### Added
- `Document.execute` enforces locks (`RegionHeld`) for every author.
- Restoring a checkpoint forks (`restore-N` lines, `core.Restore`); `side_revisions`, `history_revisions`,
  `discard_side_history`. `CommandLog.active`, `fork`, `activate`, `discard_off_path`.
- `Command.shifted_by` and `UndoConflict`: collaborative undo refuses to overwrite a colleague's later work.

### Removed
- **Breaking:** `DocumentModel.diff_to` and restore-by-inverses.

## [0.1.0] - 2026-11-02

First draft of the kernel (E1.1-E1.9): command log, `Revision(branch, seq)`, per-author undo, regions and locks,
message classes, checkpoints, redaction, manifest.
