# Changelog of claudia-fonts

Newest first. The format follows [Keep a Changelog](https://keepachangelog.com/); versions follow the versioning
policy (`docs/versioning.md`). While the major version is 0, a minor version may break the API.

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
