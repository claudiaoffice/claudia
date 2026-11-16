# Changelog of claudia-fonts

Newest first. The format follows [Keep a Changelog](https://keepachangelog.com/); versions follow the versioning
policy (`docs/versioning.md`). While the major version is 0, a minor version may break the API.

## [0.4.0] - 2026-11-16

Adding fonts through the server settings, and who may receive them (E3.13 f, D1041).

### Added
- `claudia_fonts.adding`: `check_files` (what each font of an upload, a zip opened into its fonts, would become:
  added, replacing a font of the same family and style, or left out with a reason code), `add_collection`,
  `rename_collection`, `remove_collection` (only under the root of added collections), `AddRefused`, `FileCheck`.
- `CollectionRecord.may_go` (`MayGo`, `MAY_GO`: `anywhere` or `this-server`), `added_by`, `added` and `to_data`; the
  record keeps format 1 (two optional fields were added). `FontFile.to_data` says `may_go`.
- `Problem.code`, `detail`, `family`, `style`, `collection` and `not_usable`; `FontProblem.code`, `detail`, `family`,
  `style`: why a font is not used, as a code a page can put in its own words. `Catalogue.collections` and
  `Catalogue.stands_in_for`.
- `claudia_fonts.testing.make_font` takes `licence` (the name table's licence description).

### Changed
- `redistributable: false` means "the people using this server only" (D1041), not "never handed out":
  `WebFontCache.get` makes the WOFF2 file of such a font with `local=True`.

## [0.3.0] - 2026-11-16

Fonts that take exactly the room of the common office fonts, and the words for how close a stand-in is (E3.13).

### Added
- Arimo, Tinos, Cousine (the widths of Arial and Helvetica, Times New Roman, Courier New, and of Liberation Sans,
  Serif and Mono) and Gelasio (Georgia) join the starter set, pinned at the same google/fonts commit and shipped in
  `builtin/`. Tinos has no `OFL.txt` there; its licence is in each file's name table, which a test checks.
- `DEFAULT_GENERICS`: the font of each CSS generic family and the fallback (Fraunces, Inter, JetBrains Mono, Inter).
- `CLOSENESS` and `Closeness` (`same`, `same-widths`, `other`), and `Resolution.closeness`.
- The starter set ships with the package (D500): `claudia_fonts/builtin/` holds the pinned files of
  `starter.lock.json`, `builtin_folder()` names it. A test checks the files against the lock.

### Changed
- `substitutions.json` is gone: the table, with the generic families, is `claudia_core.stand_ins`, and
  `DEFAULT_SUBSTITUTIONS` and `DEFAULT_GENERICS` are its `SAME_WIDTHS` and `GENERIC_FONTS` (claudia-core is now a
  dependency). `DEFAULT_SUBSTITUTIONS` now names
  Arimo, Tinos, Cousine and Gelasio (before: Liberation Sans, Serif and Mono, which no server had unless an operator
  added them), and Liberation Sans, Serif and Mono get the same stand-ins. The layout library's copy is generated
  from it (`scripts/generate_font_stand_ins.py`).
- The same font file found twice (the shipped set and a fetched copy) is not reported as "replaced".

### Fixed
- Fetched font files are 0644, not `mkstemp`'s 0600, so a server running as another user than the one that fetched
  them (the Docker image) can read them.

## [0.2.0] - 2026-11-12

The starter set and what clients need to lay out with a font (D905).

### Added
- `fetch`, `read_lock`, `LockedCollection`, `LockedFile`, `FetchError`: the starter set of open fonts (Inter,
  Fraunces, JetBrains Mono, Carlito, Caladea), pinned in `starter.lock.json` at a fixed commit of google/fonts and
  checked by SHA-256, fetched into one folder per collection with its `collection.json`;
  `python -m claudia_fonts fetch DIR`. The only part of the package that uses the network.
- `collection_folders`: the collections in a folder (itself, or its subfolders).
- `Axis` and `FontFile.axes`, `FontFile.outlines`: a variable font's axes and whether its outlines are TrueType or
  CFF; both are part of `FontFile.to_data()`, which clients lay out with.
- `testing.make_font(axes=...)`: a test font with an `fvar` table.

## [0.1.0] - 2026-11-03

First version (E3.3, first slice): the library of the font catalogue, outside the kernel (D26, D88).

### Added
- `Collection`, `CollectionRecord`, `COLLECTION_FILE`, `RecordError`: a folder of fonts with a `collection.json` that
  names its licence and says whether the fonts may be served to browsers.
- `read_font`, `FontFile`, `FontProblem`: one font file, read with fontTools; a file that is not a font, has no family
  name or forbids embedding is refused with a reason.
- `Catalogue`, `Problem`, `Resolution`, `DEFAULT_SUBSTITUTIONS`: all fonts of several collections, by family; the
  digest of what is in it; metric-compatible substitution (Arial to Liberation Sans and so on).
- `WebFontCache`, `NotServable`, `font_face_css`: WOFF2 for browsers, made from the same bytes the typesetting engine
  uses, only for fonts whose licence allows it; `@font-face` rules per family.
- `write_fontconfig`, `JobFonts`: a `fonts.conf` that shows an engine exactly the fonts of the catalogue.
