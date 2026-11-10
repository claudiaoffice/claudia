# Changelog of claudia-composes

Newest first. The format follows [Keep a Changelog](https://keepachangelog.com/); versions follow the versioning
policy (`docs/versioning.md`). While the major version is 0, a minor version may break the API.

## [0.1.0] - 2026-11-10

The first version under the versioning policy. Until now the package had a placeholder version (0.0.1), no
`__version__` and no API snapshot, so its surface could change without anyone noticing; from here on
`tests/api/claudia_composes.json` holds it to the rules of `docs/versioning.md`. This entry records the surface as it
stands, not a history of how it got there.

### Added
- `__version__`.
- The text: `TextModel` with its paragraphs (`Block`, the core `Paragraph` under its old name) with their authorship runs, styles (`BUILTIN_STYLES`,
  `DEFAULT_STYLE`, `builtin_styles`, `next_style`) and floating objects anchored to a paragraph (`TextObject`,
  `BlockAnchor`).
- This app's commands (`TextCommand`): `InsertText`, `DeleteText`, `SplitBlock`, `JoinBlocks`, `SetStyle`, and the
  suggestions of D63 (`Suggestion`, `ProposeSuggestion`, `AcceptSuggestion`, `ResolveSuggestion`).
- Regions: `TextRange`, and `word_window`, the ± n words around a cursor (D11).
- Re-exported from `claudia_core`: the shared object commands and types (`AddObject`, `MoveObject`, `ResizeObject`,
  `RotateObject`, `RemoveObject`, `SetSnap`, `SetText`, `SetParagraphStyle`, `DefineImage`/`ForgetImage`,
  `DefineShape`/`ForgetShape`, `ObjectBody`, `VisualObject`, `ObjectSet`, `Paragraph`, `Run`, `paragraph_for`).
