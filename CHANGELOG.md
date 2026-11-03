# Changelog

All notable changes to the public API of `claudia-core` are listed here, newest first. The format follows
[Keep a Changelog](https://keepachangelog.com/); versions follow the versioning policy (`docs/versioning.md`).
While the major version is 0, a minor version may break the API; every break is marked **Breaking**.

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
