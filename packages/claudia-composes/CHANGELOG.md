# Changelog of claudia-composes

Newest first. The format follows [Keep a Changelog](https://keepachangelog.com/); versions follow the versioning
policy (`docs/versioning.md`). While the major version is 0, a minor version may break the API.

## [Unreleased]

### Added
- Tables in a text (E9.32): the text holds table definitions (`TextModel.tables`, state schema 15), shows them with
  objects of the kind `table`, takes typing in a box with the ordinary text commands on the box's paragraph id, locks
  a typed-in box as a `TableRegion`, and has three built-in looks (`TABLE_LOOKS`, `DEFAULT_LOOK`) whose twelve styles
  are `BUILTIN_STYLES` (`TABLE_STYLE_IDS`).

### Added
- `TextModel.restyle_users(old, new)`: the commands that put the paragraphs and objects that have a style under another
  (the deletion of a style, E1.10, D226). Its built-in styles have `origin == "builtin"`.

## [0.18.0] - 2026-11-17

References (step H).

### Added
- `TextModel.fields_of` and `put_fields` (the text is a `claudia_core.FieldHost`); the event `FieldsPut` (wire type
  `block_fields`). Splitting and joining share out a paragraph's fields by their characters.

### Changed
- **Breaking:** `TextModel.insert` takes the fields of the U+FFFC put in, `remove` returns those cut; `insert_text` and
  `remove_text` follow `claudia_core.TypingHost`.

## [0.17.0] - 2026-11-17

Typing is the kernel's (step G).

### Changed
- **Breaking:** `InsertText` and `DeleteText` are `claudia_core.InsertText` and `claudia_core.DeleteText`
  (`core.InsertText`, `core.DeleteText`, field `paragraph`); `composes.InsertText` and `composes.DeleteText` are gone
  and old command logs with them do not replay (the owner's decision of 2026-11-16; snapshots still open).
  `TextCommand` and `Span` are `claudia_core`'s, still importable from here.

### Added
- `TextModel.insert_text`, `remove_text`, `text_regions` and `text_moved`: the text is a `claudia_core.TypingHost`, for
  its paragraphs and the words of its floating objects.

## [0.16.0] - 2026-11-17

Tables of contents (step E, E9.31). State schema 13 → 14 (a paragraph may have `generated`; a snapshot of 13 restores
unchanged).

### Added
- `TextModel.generated_of` and `put_generated`: the text is a `claudia_core.GeneratedHost`, for its own paragraphs and
  the words of its floating objects; the event `BlockGenerated` (wire type `block_generated`).
- The built-in styles Contents Title (`contents-title`) and Contents 1 to 9 (`contents-1` … `contents-9`), which the
  entries of a table are drawn in.

### Changed
- Typing into a table of contents and joining a paragraph with text into one are refused; a table cannot be joined to
  the paragraph before it (it is taken away instead).

## [0.15.0] - 2026-11-16

Numbered headings and numbering schemes (step D, E9.22). State schema 12 → 13 (a snapshot of 12 restores with the
built-in schemes).

### Added
- `TextModel.schemes` (a `claudia_core.SchemeBook`, in the state as `schemes`); `item_of`, `put_item` and
  `item_regions`: the text is a `claudia_core.ItemHost`, for its own paragraphs and the words of its floating objects.
- A paragraph whose style is numbered (`StyleDef.numbering`) gets a label like a list item: numbered headings.
- `JoinBlocks.ends_paragraph`.

### Changed
- **Breaking:** `SetListItem` is `claudia_core.SetListItem` (`core.SetListItem`, field `paragraph`);
  `composes.SetListItem` is gone and old histories with it do not replay (the owner's decision of 2026-11-16).
- `list_in_use` counts the words of floating objects too.

## [0.14.0] - 2026-11-16

The text counts with the structure every app shares (step C).

### Added
- `TextModel.reading_order()`, `TextModel.structure_version` and `TextModel.structure` (a `claudia_core.TextStructure`):
  the text is a `ParagraphHost`. Its paragraphs are read in order, each followed by the words of the objects that hang
  from it, in stacking order; only its own paragraphs are its main text.
### Changed
- `TextModel.labels()` comes from the shared structure and also counts the words of the objects: an object's words that
  are an item of a list count between the paragraph they hang from and the next one.
- `LabelsChanged` is `claudia_core.LabelsChanged`; the name stays importable from here.

## [0.13.0] - 2026-11-16

Headings by their level (E9.22). State schema 11 → 12 (a snapshot of 11 is rebuilt from the log, D15).

### Added
- Heading 3 to Heading 6 are built-in styles. The title has heading level 0 and Heading 1 to 6 levels 1 to 6.
- `TextModel.heading_level(block)`: a paragraph's heading level, from its style.
### Changed
- A paragraph is a heading because its style gives a heading level, not because its style is (or is based on) the title
  or Heading 1 or 2; the module constant `HEADING_STYLES` is gone. `block_kind` and the sections of a search follow the
  level, so a style of the writer's own becomes a heading by `SetHeadingLevel`, and a section starts at any heading of
  level 1 or deeper.
## [0.12.0] - 2026-11-16

### Added
- `blank(parts)` on the model (D723): an imported document is redacted in full or in parts — the paragraphs (by id) and objects; a blanked paragraph keeps its length in `FILLER` characters and its suggestions lose their words.

## [0.11.0] - 2026-11-15

Objects float (D1023).

### Added
- `BlockAnchor.dx` and `BlockAnchor.dy` (default 0): how far to the right and down the top-left corner of an object lies
  from the character it hangs from, in CSS pixels, at most `MAX_ANCHOR_OFFSET` (10 000) either way. The offset follows
  the anchor through typing, splitting and joining paragraphs and undo; only moving the object changes it.
- `BlockAnchor.carried_to` and `check_floating`; `MAX_ANCHOR_OFFSET`.
### Changed
- `BlockAnchor.to_data` carries `dx` and `dy`. An anchor written before them reads as sitting on its character, so
  older documents and logs open unchanged. Placing an object where it hangs (D907) now adds the offset.

## [0.10.0] - 2026-11-15

Paragraphs are things (D554).

### Added
- A paragraph is a thing (D554): `TextModel.block_names` (state schema 11), `block_kind` (`heading`, `item`,
  `paragraph`), and `named_things`, `thing_name`, `set_thing_name`, `has_thing` for paragraphs; `RenameThing` names one.
  Paragraphs are not among `unnamed_things`: they are named one at a time, when somebody points at one.
## [0.9.0] - 2026-11-15

Names of things (D550).

### Added
- Objects carry a `name` (`ObjectBody.name`) and are renamed with `RenameThing`, both from `claudia_core`.

## [0.8.0] - 2026-11-14

Search and replace (E9.28).

### Added
- The Help topic `composes.searching-and-replacing`, in English and German (E9.28).
- `claudia_composes.search` (not in `__all__`; the server's): the texts of a text for a search (`text`, `heading`
  and `remark` by the style of a paragraph and the styles it is based on, the words and the descriptions of floating
  objects), the scopes whole text, section and selection, the part `word`, and `plan_replacement` and
  `replace_command`: a replacement is stored as typing and deleting, so the words around a match keep their authors
  and the objects hanging in a paragraph keep their words. Depends on `claudia-search`.

Lists (E9.21), earlier in this release.

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

## [0.7.0] - 2026-11-13

### Added
- Rendered text containers in text documents (D390): definitions and their commands in the model, `state_schema`
  10. There is no way to place one on the wire yet.

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
