# Changelog of claudia-test-documents

Newest first. The format follows [Keep a Changelog](https://keepachangelog.com/); versions follow the versioning
policy (`docs/versioning.md`). While the major version is 0, a minor version may break the API.

## [0.1.0] - 2026-11-10

The first version under the versioning policy. Until now the package had a placeholder version (0.0.1), no
`__version__` and no API snapshot, so its surface could change without anyone noticing; from here on
`tests/api/claudia_test_documents.json` holds it to the rules of `docs/versioning.md`. This entry records the surface
as it stands, not a history of how it got there.

### Added
- `__version__`.
- The three-tier check of one case: `Case`, `Model`, `run_case`, `RunResult` (D218).
- The per-format adapters: `Adapter`, `ADAPTERS`; `load_case` loads a case's `spec.py` safely.
- The catalogue file: `Entry`, `load_catalogue`, `save_catalogue`, `select`, `record_run`.
