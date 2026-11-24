# Changelog of claudia-opc-io

Newest first. The format follows [Keep a Changelog](https://keepachangelog.com/); versions follow the versioning
policy (`docs/versioning.md`). While the major version is 0, a minor version may break the API.

## [Unreleased]

### Added
- `claudia_opc_io.custom`: `custom_properties(parts)` and `set_custom_properties(parts, values)`, the text properties of
  `docProps/custom.xml` (the part declared and related once), `CUSTOM_PART` (E6.31, D1478).
- `claudia_opc_io.drawingml`: what a DrawingML drawing says of itself in a docx, xlsx or pptx alike: `turn_of`,
  `cropped`, `shown_part`, `is_decorative`, and `DRAWINGML`, `ANGLE`, `EMU_PER_PIXEL`, `SVG_URI`, `DECORATIVE_URI`
  (D1478; composes' docx readers had them).

## [0.5.0] - 2026-11-17

A package is judged before it is unpacked, and its XML is read without entities (SEC-15).

### Added
- `claudia_opc_io.limits`: `PackageLimits` (members, part size, total size, and how many times a part may compress),
  `DEFAULT_LIMITS`, `check_package(data, limits)` and `PackageRefused`. The sizes come from the archive's directory,
  so a zip bomb is refused before one byte of it is unpacked.
- `claudia_opc_io.xml`: `parse_xml(data)`, lxml with entities never resolved, no network and no DTD, for every reader
  of a package's XML. The package now depends on `lxml>=5`.

### Changed
- `read_parts(data, limits=DEFAULT_LIMITS)` calls `check_package` first and raises `PackageRefused` for a package over
  the limits (new optional parameter).

## [0.4.0] - 2026-11-17

The properties of an OPC package (D466).

### Added
- `claudia_opc_io.properties`: `stamp_core_properties(parts, *, created, creator, modified, modifier)` writes
  `docProps/core.xml` and `docProps/app.xml` of a package's parts, `stamp_package(data, ...)` does it to package bytes,
  `utc_second(moment)` is a moment in W3CDTF UTC to the second; `CORE_PART` and `APPLICATION` ("Claudia").

## [0.3.0] - 2026-11-16

### Added
- `ThemeFonts`: the heading and body fonts of an Office theme, and the font a reference to one names in Word's
  notation (`minorHAnsi`) and PowerPoint's (`+mn-lt`), for the docx and pptx importers (E3.13).

## [0.2.0] - 2026-11-11

### Changed
- `write_parts` follows the one rule of OpenDocument packages that is a rule of the zip (ODF 1.3 part 3, 3.3; D401):
  a part named `mimetype` is written first and stored, not compressed, so that `file`, browsers and upload filters can
  read the type of a document at a fixed place in it. A package without that part is written as before.
- Every part is written with the same timestamp (1980-01-01), so the same parts always give the same bytes: an OOXML
  or OpenDocument file no longer differs from its twin by the clock. The parts themselves are unchanged.

## [0.1.0] - 2026-11-10

The first version under the versioning policy. Until now the package had a placeholder version (0.0.1), no
`__version__` and no API snapshot, so its surface could change without anyone noticing; from here on
`tests/api/claudia_opc_io.json` holds it to the rules of `docs/versioning.md`. This entry records the surface as it
stands, not a history of how it got there.

### Added
- `__version__`.
- `read_parts`/`write_parts`: a zip package as a plain dict of its parts, and back.
- `owns`/`reconcile` (with the `OwnedTest` predicate type): restore whatever a format library's `save()` was not
  asked to touch (D217).
