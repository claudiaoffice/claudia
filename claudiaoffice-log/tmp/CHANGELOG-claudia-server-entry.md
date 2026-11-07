Prepend this entry to the top of `packages/claudia-server/CHANGELOG.md`, directly above the existing `## [0.10.0] - 2026-11-06` entry (note: that file already has `0.9.0` twice, out of order — pre-existing on `main`, unrelated to this patch; left alone). Required for `tests/test_public_api.py::test_the_version_is_in_the_changelog[claudia_server]` to pass once this patch and this entry are both applied.

---

## [0.11.0] - 2026-11-07

I18n groundwork (E5.7, D31, D141): the wire protocol learns the connection's own locale and gains a finer-grained
error detail, both additive.

### Added
- **`locale` in `hello`** (optional) and **in `welcome`** (always): the client's own locale (OS/browser default,
  or whatever the person picked in their own client — never a server-side setting, since a document's users are
  scoped to the document, D35, with no account profile to keep it on). `protocol.normalize_locale` falls back to
  `DEFAULT_LOCALE` ("en") for anything missing, not a string, too long, or not shaped like a BCP-47-ish tag — never
  refuses the connection over it. `Context.locale`: carried through to every method, though nothing reads it yet.
  `PROTOCOL_VERSION` is now 2.
- **`RequestError.detail`** (optional): the finer-grained `claudia_core` error `code` behind a wire-level `code`
  (`"locked"`, `"stale"`, `"conflict"`...), included in `to_dict()`/the wire response only when given. `message`
  stays the English sentence for anyone not yet rendering from `code`/`detail`; a future translator uses `detail`
  (or the method-level `code`, for anything that is not a `KernelError`) to pick the message to show instead.
  `MethodTable.dispatch` now passes it for `StaleEdit`, `RegionHeld`/`UndoRefused`, `UndoConflict` and any other
  `KernelError`.

### Changed
- `Connection.__init__` and `HostedDocument.connect` take an additional optional `locale` parameter (additive,
  default `DEFAULT_LOCALE`: no behaviour change for a caller that does not pass one).
