# Changelog of claudia-composes

Newest first. The format follows [Keep a Changelog](https://keepachangelog.com/); versions follow the versioning
policy (`docs/versioning.md`). While the major version is 0, a minor version may break the API.

## [Unreleased]

Lists (E9.21). State schema 7 → 8. Describing objects (BITV 1.1.1): schema 8 → 9.

### Added
- `DescribeObject` is exported (it is the kernel's, `claudia_core.DescribeObject`); object bodies carry `description`
  and `decorative` (see the core changelog).
- `SetListItem(block, item)`: make a paragraph an item of a list at a level, or a plain paragraph again.
- `TextModel.lists` (a `ListBook`), `TextModel.labels()` (the marker of every item, derived and cached until the
  structure or the lists change), `TextModel.list_in_use` and `TextModel.set_item`.
- The events `ItemChanged` (`item`) and `LabelsChanged` (`labels`: only the paragraphs whose marker differs from what
  clients were last told; typing sends none).

### Changed
- `SplitBlock` gives the new paragraph the item of the one it cuts (Enter in an item makes an item); `JoinBlocks`
  keeps the first paragraph's item, and when the paragraph that went away was a different kind of item its inverse is
  a `Batch` of the split and a `SetListItem`, so undo is exact. `TextModel.join` returns the paragraph that went away
  (it returned its style).
- The state has a `lists` entry; a state without one (schema 7 and earlier) opens as a text without lists.

### Added (UX-33)
- `TextModel.setup_commands`: a new text starts in the language of its maker's interface (D915), set by the server as nobody's undo step (UX-33). The web client no longer sets it.

## [0.6.0] - 2026-11-13

The page setup and the language are the kernel's (D917).

### Changed
- `PageSetup`, `PageSetupError`, `PAPERS`, `normalize_language`, `LanguageError`, `SetLanguage` and
  `LanguageChanged` are `claudia_core`'s; `claudia_composes` and its `page` and `language` modules re-export them, so
  imports keep working. `PAPERS` lists the paper `slide` too (a text is not offered it).
- **Breaking (log format, read compatibly):** a language change is written as `core.SetLanguage`. Logs that wrote
  `composes.SetLanguage` still replay, through an alias command registered under the old kind.

## [0.5.0] - 2026-11-12

The language of a text, and hyphenation (D912, D915).

### Added
- `TextModel.language`: the language the text is written in, a BCP 47 tag, or `None` (a new text, and every older
  one); state schema 7.
- `SetLanguage(language)`: one step with its exact inverse (summary "set the language to de-AT"), event
  `{type: "language", language}`; `normalize_language` and `LanguageError` check and write a tag as BCP 47 does
  (`en-gb` becomes `en-GB`).

### Changed
- The built-in styles say how they hyphenate (`hyphens`, CSS_VERSION 4): Body text and the styles based on it
  `auto`, Title and the headings `manual`. A text keeps the styles it was made with, so only new texts have this.

## [0.4.0] - 2026-11-12

The page a text is printed on (E9.14 first step; print preview, D904).

### Added
- `PageSetup`, `PageSetupError`, `PAPERS`: paper (a preset such as `a4` or `letter`, or `custom`), orientation,
  margins and page numbers, every length in mpt (the layout library's unit); checked so the margins leave room.
- `SetPageSetup`: one step that changes the page, with its exact inverse; it raises a `page` event.
- `TextModel.page`, stored with the text (state schema 6; an older state gets A4 portrait, 2.5 cm margins).

## [0.3.0] - 2026-11-10

The styling-suite plan, steps 1.2 to 1.6.

### Added
- The built-in **`plain-box`**, a `box` style without properties: the box of a text box on the text (D310).

### Changed
- **Breaking:** a paragraph takes only a style that fits it — a `paragraph` style (D304, D316); `SetStyle` and
  `split` refuse `plain-shape`, `plain-box` and `plain-image`.
- `TextModel.style_in_use` also counts the objects in the text and their words, so a style only an object uses
  cannot be taken back.

## [0.2.0] - 2026-11-10

Every built-in style has a kind (D305, D312), and a shape's outline and its words are two styles (D310).

### Changed
- **Breaking:** the paragraph styles are `paragraph` styles (Definition keeps its box: a paragraph style may hold
  one). `plain-shape` is an `outline` style (`fill`, `stroke`, `stroke-width` only, no parent); its words' centring
  moved to the new built-in **`shape-label`**. `plain-image` is a `box` style.

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
