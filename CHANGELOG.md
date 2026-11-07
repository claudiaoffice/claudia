# Changelog

All notable changes to the public API of `claudia-core` are listed here, newest first. The format follows
[Keep a Changelog](https://keepachangelog.com/); versions follow the versioning policy (`docs/versioning.md`).
While the major version is 0, a minor version may break the API; every break is marked **Breaking**.

## [0.6.0] - 2026-11-07

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

### Notes for implementers
- `ImageAsset.to_data()`/`from_data()` carry the image's bytes as base64 text, because a document's state and the
  server's wire protocol are both JSON (there is no binary attachment channel). A document with many or large
  images can approach the protocol's 16 MB message limit on a plain `snapshot` request; that is an accepted
  limitation of embedding images in the document state (there being no separate blob store yet, see the E2
  container format), not something this change solves.
- `ImageImport`'s redaction story is intentionally not addressed here: it is covered by the project's open decision
  on redaction in general, not decided as a side effect of adding images.
Go back to a checkpoint, with everybody's consent (E3.7): the live session needs a read-only preview of a line
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
