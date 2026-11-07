Prepend this entry to the top of `CHANGELOG.md` (root), directly above the existing `## [0.5.0] - 2026-11-03` entry. Required for `tests/test_public_api.py::test_the_version_is_in_the_changelog[claudia_core]` to pass once this patch and this entry are both applied.

---

## [0.5.1] - 2026-11-07

I18n groundwork (E5.7, D31, D141): the kernel gains stable error identity, without taking on gettext or any other
translation dependency itself.

### Added
- `KernelError.code` and a unique `code: ClassVar[str]` on every subclass (`unknown_command`, `schema_too_new`,
  `missing_upcaster`, `revision_mismatch`, `region_held`, `stale_edit`, `undo_refused`, `undo_conflict`,
  `redaction_error`, `replay_error`): a machine-readable identity for each error, independent of `str(exc)`'s
  baked English sentence. A future translator picks the message to show from `code`; the kernel itself still does
  not import gettext or know any catalog exists (`test_purity.py`).
- `MissingUpcaster` now also carries `self.kind` and `self.schema` (previously only in the message text).

Invisible to `scripts/api_surface.py` (it inspects callable signatures and `property` instances only, not plain
`ClassVar` attributes), so this is not a signature change — the version bump and this entry are about the new
machine-readable contract, not a surface the snapshot would have caught on its own.
