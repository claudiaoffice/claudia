# Changelog of claudia-opc-io

Newest first. The format follows [Keep a Changelog](https://keepachangelog.com/); versions follow the versioning
policy (`docs/versioning.md`). While the major version is 0, a minor version may break the API.

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
