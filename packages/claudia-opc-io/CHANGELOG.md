# Changelog of claudia-opc-io

Newest first. The format follows [Keep a Changelog](https://keepachangelog.com/); versions follow the versioning
policy (`docs/versioning.md`). While the major version is 0, a minor version may break the API.

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
