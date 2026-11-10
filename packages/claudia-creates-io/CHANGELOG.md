# Changelog of claudia-creates-io

Newest first. The format follows [Keep a Changelog](https://keepachangelog.com/); versions follow the versioning
policy (`docs/versioning.md`). While the major version is 0, a minor version may break the API.

## [0.1.0] - 2026-11-10

The first version under the versioning policy. Until now the package had a placeholder version (0.0.1), no
`__version__` and no API snapshot, so its surface could change without anyone noticing; from here on
`tests/api/claudia_creates_io.json` holds it to the rules of `docs/versioning.md`. This entry records the surface as
it stands, not a history of how it got there.

### Added
- `__version__`.
- `slides_to_pptx`, `pptx_to_slides`, and `apply_edits_to_pptx` (D219), which raises `UnsupportedEdit` for what it
  cannot patch.
- `add_transition`: a slide transition, written into the slide part's XML (D147).
