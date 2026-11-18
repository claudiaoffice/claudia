# Changelog

All notable changes to the public API of `claudia-core` are listed here, newest first. The format follows
[Keep a Changelog](https://keepachangelog.com/); versions follow the versioning policy (`docs/versioning.md`).
While the major version is 0, a minor version may break the API; every break is marked **Breaking**.

## [Unreleased]

### Added
- `MAX_WIDTH` and `MIN_WIDTH`, the limits of the width of a table and of a column (hundredths of a percent), are
  exported from the package (E9.32).
- Tables (E9.32, D1201–D1210): `TableDef` (rows, columns, boxes of one paragraph each with the id `table/row/column`,
  merged rectangles, header rows, banding, a look, flow or float placement, at most `MAX_ROWS` × `MAX_COLUMNS`),
  `Column`, `Merge`, `RowSpec`, `ColumnSpec`, `TableLook`, `TableRegion`, the protocol `TableSource`, and the commands
  `DefineTable`, `ForgetTable`, `SetEntries`, `InsertRows`, `DeleteRows`, `InsertColumns`, `DeleteColumns`,
  `SetRowOrder`, `SetColumnOrder`, `SetColumn`, `SetTableOptions` and `SetMerge`, with the event `TablesChanged`. An
  undo is refused when a colleague typed into a box it would destroy. `ObjectModel` holds `tables` and the kind
  `"table"` is one of `OBJECT_KINDS`; the facet slots have a `table` thing.

### Changed
- **Breaking:** `ObjectBody` points at its definition with one field, `ref`, whose table the kind names, instead of one
  field per kind (`shape`, `image`, `diagram`, `rendered`, `table`). The five names stay as read-only properties
  (`body.image` is `body.ref` for an image, else `None`), so readers keep working; code that builds a body or changes
  one with `replace` says `ref=`. A new kind of object needs no new field. The plain data has `ref` and none of the
  five; bodies written the old way still read (`ObjectBody.from_data`), and `core.AddObject` is schema 6 with an
  upcaster. The checks say "a text box points at no definition" and "this document does not know the image 'x'" where
  they said that another kind's field was set.

### Added
- Deleting and hiding styles (E1.10, D226, D785): `plan_delete_style(model, style_id, *, how="assign", target=None)`
  plans a deletion as one `Batch` that is undone as one. `how` is one of `DELETE_HOWS`: `"assign"` (what has the style
  and what is based on it goes to `target`, a style of the same kind; the one way that changes looks, which
  `assign_changes_look` says beforehand; `StyleBook.fallback` is the plain style of the kind a dialog offers first) or
  `"rebase"` (everything keeps its look, built on `target`; what had the style itself goes to a stand-in). `target`
  may be left out only for a style nothing has and nothing is based on. `held_look` says what a style must set itself
  to look the same under another parent, `INITIAL_CSS` gives the value of "nothing" for the properties where it is
  the same in every app. New commands `RebaseStyle` (kind `core.RebaseStyle`) and `SetStyleHidden`
  (`core.SetStyleHidden`).
- `StyleDef.origin` (`"document"`, `"builtin"` or `"template"`, `ORIGINS`) and `StyleDef.hidden`; only a document
  style can be deleted, the others only hidden. Both are written only when they are not the default, so a style
  without them writes what it wrote before. `StyleBook.set_hidden`, `rebase` and `next_after`; `StyleBook.add` takes
  `before`; `CreateStyle` takes `before`.
- `ObjectModel.restyle_users(old, new)`: the commands that put the objects that have a style under another. An app's
  model that has styles and `style_in_use` offers it too, or a style in use cannot be deleted.
- `claudia_core.stand_ins` (E3.13, CODE-42): `GENERIC_FONTS` (the font of each CSS generic family and the fallback),
  `GENERIC_ALIASES` (every CSS name for a generic family), `SAME_WIDTHS` (open fonts that take exactly the room of a
  common office font), `generic_font` and `file_font` (the font an office file names for a `font-family` list). The
  one source of these facts: `claudia_fonts` builds on it, and the layout library's copy is generated from it.
- `claudia_core.stand_ins.css_family` (E3.13, bugs 1 and 2): the CSS `font-family` list for a font an office file
  names, with the generic family it falls back to (`'Times New Roman', serif`). The importers of all three apps use
  it; the serif and monospace lists of `claudia_computes_io` moved here.

### Changed
- `StyleBook.to_data` always writes a parent before its children, whatever order styles were re-based into.
- The undo of `RemoveStyle` puts the style back where it was in the book, not last.

## [0.36.0] - 2026-11-18

The redaction screens (E3.14, D729).

### Added
- `RedactionPlan.regions`: the places on the line people see that the blanked steps touch, for a preview to mark
  (empty when nothing people see changes).

### Changed
- `Document.plan_redaction`: a later step whose blank of the same shape still does not apply becomes a no-op tombstone
  instead of stopping the redaction (D729). The last resort is a history that does not replay before any blanked step.

## [0.35.0] - 2026-11-17

References (step H of `claudiaoffice-log/notes/text-structure-across-apps.md`).

### Added
- `claudia_core.fields`: a field sits at one U+FFFC of a paragraph's text (`FIELD_CHAR`); `RefField` (kind `ref`: the
  id of what it points at and what it shows, `SHOWS`), `Field`, `field_from_data`, `fields_before`, `plain` (words
  without U+FFFC), `Shown` and the event `FieldsChanged` (wire type `fields`), `FieldHost`, and the command `SetField`
  (`core.SetField`, Show As).
- `Paragraph.fields`, `typed`, `cut` and `with_fields`: the fields go with their characters; `check` says so. Its wire
  form has `fields`.
- `InsertText.fields`: the fields of the U+FFFC it puts in (a reference put in, a delete's fields put back).
- `TextStructure.shown()`: what every field reads as, derived (a target's number, words, both, its place, its name;
  `broken` when it is gone); `settle` reports changes as `FieldsChanged`.
- `ObjectModel.object_fields` and `put_object_fields`.

### Changed
- **Breaking:** `TypingHost.insert_text` takes the fields and `remove_text` returns them;
  `ObjectModel.insert_object_text` and `remove_object_text` likewise.
- `SetText` and `replace_spans` take words: a U+FFFC in them makes no field, and the fields of the words they replace
  go with them (an undo puts them back).

## [0.34.0] - 2026-11-17

Typing into any paragraph (step G of `claudiaoffice-log/notes/text-structure-across-apps.md`, section 3.1).

### Added
- `claudia_core.writing`: `InsertText` (`core.InsertText`) and `DeleteText` (`core.DeleteText`) type into and delete
  from any paragraph, character by character, keeping who wrote which part; the model says how through `TypingHost`
  (`insert_text`, `remove_text`, `text_regions`, `text_moved`). `TextCommand` and `Span` (moved from
  `claudia-composes`): how a stretch of text follows other people's edits. `word_changes` gives the steps that turn
  some words into others by changing only what differs.
- `ObjectModel.insert_object_text` and `remove_object_text`: typing into the words of an object.

### Fixed
- Undo (CODE-57): a step undone or redone by the very next entry is left out with it when an older step is followed
  forward, so undoing typing after an undone delete that cut into it takes out exactly the typing.

## [0.33.0] - 2026-11-17

Tables of contents and agendas, generated paragraphs (step E of `claudiaoffice-log/notes/text-structure-across-apps.md`,
E9.31).

### Added
- `claudia_core.generated`: `Toc` (the options of a table of contents: the heading levels `first` to `last`, `numbers`,
  `places`, `leader`), `Generated`, `generated_from_data`, `ContentsEntry` (an entry: its target paragraph, level,
  number, words, style `contents-<level>` and, when known, its place), `GeneratedChanged` (wire type `generated`, the
  entries of a table or `None` when it went away), `GeneratedHost` and the command `SetGenerated`
  (`core.SetGenerated`), which makes a paragraph a table of contents with these options, or a plain paragraph again.
  `CONTENTS_STYLE`.
- `Paragraph.generated` and `Paragraph.with_generated`: a generated paragraph stores only its options and holds no text;
  its wire form has `generated`.
- `TextStructure.outline()`, `all_entries()` and `entries(paragraph)`: the headings of levels 1 to 9 of the main text in
  reading order, and every table's entries derived from them; `settle` reports changed entries as `GeneratedChanged`.
- `ObjectModel.object_generated` and `put_object_generated`: the words of an object can be an agenda; `SetText` refuses
  words for one.

## [0.32.0] - 2026-11-16

Numbering schemes as document data, numbered headings, list items on any paragraph (step D of
`claudiaoffice-log/notes/text-structure-across-apps.md`, E9.22).

### Added
- `claudia_core.schemes`: `LevelFormat` (a level's number format or bullet, the text before and after it, and the
  first level whose counter it shows), `Scheme` (nine levels, an indent and a gap), `SchemeBook` (what a model holds as
  `schemes`; a new book has the built-in `bullets`, `numbers` and the new `chapters`, 1, 1.1, 1.1.1), `builtin_schemes`,
  `builtin_scheme`, `FORMATS`, and the commands `CreateScheme`, `ChangeScheme`, `RemoveScheme` (refused while a list
  uses the scheme) with the event `SchemesChanged` (wire type `schemes`). `SchemeBook.drawing` finds or makes the scheme
  that draws some levels, as a file's list is read.
- `StyleDef.numbering` (a list id, `NO_NUMBERING` or `None` as the parent) and `StyleBook.numbering`, `StyleBook.version`;
  `StyleBook.views` sends `numbered`. `SetStyleNumbering` numbers a heading style in a list.
- `SetListItem` (`core.SetListItem`, moved from `claudia-composes`): any paragraph becomes a list item, a paragraph of a
  text or the words of an object; the model says how through `ItemHost` (`item_of`, `put_item`, `item_regions`).
  `ObjectModel.object_item`, `put_object_item` and `object_list_in_use` do it for the words of objects.
- `Command.ends_paragraph`: whether a command makes a paragraph part of another or takes it away (a join, removing an
  object), so that an item set on it cannot be undone past it.
- `Label.number`: the trail a reference prints ("2.a"); the wire form of a label has `number`.
- `TextStructure.items()` and effective items: a paragraph of the main text whose style gives a heading level of 1 or
  more and names a list is an item of that list at the level below its heading level, unless it has an item of its own.
  `ParagraphHost` has `schemes`; the labels are worked out again when the styles or the schemes change too.

### Changed
- **Breaking:** `SCHEMES` and `lists.Scheme` are gone: the schemes are the document's (`SchemeBook`).
  `numbering_labels(entries, lists, schemes)` takes the scheme book. `ListDef.check` checks the scheme's id only; that
  the scheme exists is checked by `CreateList` and `ChangeList` against the model's `schemes`, which a model that
  holds lists now needs. `TextStructure.effective_item` takes a `Placed`.
- `RemoveList` is refused while a style is numbered in the list.

## [0.31.0] - 2026-11-16

The text structure every app shares (step C of `claudiaoffice-log/notes/text-structure-across-apps.md`).

### Added
- `ParagraphHost` and `Placed`: what an app gives the shared structure: its paragraphs in reading order (each with its
  container, whether it is part of the main text, and the place a reader finds it at when the app knows it), its style
  and list books, and a `structure_version`.
- `TextStructure` (and `Emitter`, what its `settle` tells clients through): the label of every list item, counted in reading order across containers, kept until the structure
  or the lists change, and `settle`, which tells the clients what changed.
- `LabelsChanged` (moved here from `claudia-composes`, the same wire form): the labels of paragraphs of a text and of the
  words of objects, by paragraph id.
- `ObjectModel.paragraph_order`: changes when an object comes, goes, moves to another container, or its words become
  another list item or take another style; typing does not change it.

## [0.30.0] - 2026-11-16

Heading levels (E9.22, step B of `claudiaoffice-log/notes/text-structure-across-apps.md`).

### Added
- `StyleDef.heading_level` (default `None`): the heading level a paragraph style gives its paragraphs: 0 the title, 1 to
  `MAX_HEADING_LEVEL` (9) a section, `"body"` none whatever the parent gives, `None` as the parent does. Written only when
  set, so a style without one writes what it wrote before. Only a paragraph style can have one. `HeadingLevel`.
- `StyleBook.heading_level(style_id)`: the level a style gives, its parents taken in; `StyleBook.set_heading_level`.
- `StyleBook.views` carries `heading`, that level worked out, so that no client, layout or exporter walks the parents
  or keeps a list of heading styles by name.
- `SetHeadingLevel(style, level)`: the command, with its exact inverse; refused for another level or a style that is not
  a paragraph style.
## [0.29.0] - 2026-11-17

The looks helpers and the box of a file, shared by composes and creates (D465).

### Added
- `points_of`, `colour_of`, `parse_colour`: how a style's length and colour become points and RGB, moved here from
  `claudia-creates-io` so that composes writes the look of a box the same way creates does (`claudia_creates_io` still
  has them).
- `PRIMITIVES`, `primitive(shape_id)`: the three shapes a file has an outline for (circle, rectangle, triangle) and
  their definition in the model.
- `TEXT_BOX_STYLE`, `SHAPE_STYLE`, `SHAPE_LABEL_STYLE`, `box_body(...)`: the object and paragraph styles a text box
  or shape read from a file gets, and the object body built from it.

## [0.28.0] - 2026-11-16

The redaction contract (D229, D720–D728, E1.8).

### Added
- `Document.plan_redaction(revisions, *, chat, parts)` and `RedactionPlan` (D721, D722): what a redaction does,
  worked out before anything changes — the blanked form of every step, the later steps that stop working without the
  content (`dependents`, blanked too), the chat messages, the imports, whether the document as people see it changes
  (`changes_now`) and that state (`after`). Steps on hidden lines may be redacted (D724); every line that holds a
  blanked step must still replay.
- `Command.redacted_in(model)`: the blanked form for a command whose content only the app can judge. `Import` blanks
  its state through the model (`Import.blanked(model, parts)`, D723), `DefineDiagram` and `UpdateDiagram` through
  `ObjectModel.blank_diagram`.
- `DocumentModel.blank(parts)` (D723): blank content in place, keeping ids, places and lengths; the default refuses.
  `ObjectModel.blank_objects(parts)` does it for the objects of all three apps. `FILLER` is the character a blanked
  character becomes.
- `ChatRecord.redacted` and `ChatRecord.blanked()`; `Redaction.chat` and `Redacted.chat` (D724). A record or event
  without chat reads and writes as before.
- `ImageAsset.blanked()` and `ImageImport.blanked()` (D720): a redacted picture keeps its id and size, not its pixels;
  an import record keeps who and when, not the alternative text or the file's name and path.
- `CommandLog.line(name)`: the entries of one line itself.

### Changed
- **Breaking:** `Document.redact(what, *, author)` takes a `RedactionPlan` or a bare list of steps; a bare list is
  refused when other steps would have to be blanked with it (D722). The store is rewritten (`DocumentStore.rewrite`).
- **Breaking:** `DocumentStore.replace_entries` and `drop_snapshots` are replaced by `rewrite(log, chat)` (D725): the
  store holds exactly the redacted log and chat afterwards, with no copy of the content left.
- `DefineImage.redacted()` blanks the picture; `AddObject.redacted()` also takes the description and the words of the
  import record (D720).

## [0.27.0] - 2026-11-15

Turning objects (D1021–D1024).

### Added
- `claudia_core.turning` (`SINE_MILLIONTHS`, `turned_extent`, `nudge_into`): how far a turned frame reaches, in whole
  units and from an integer table of sines (D910), and the nearest place at which a turned outline lies inside a space.
- `ObjectModel.turn_command(id, rotation)`: the command that turns an object. Any whole number of degrees is read
  modulo a whole turn (-20 is 340); a chart (kind `diagram`) does not turn (`ObjectModel.can_turn`); the command carries
  the place the object has to be moved to for its outline to be allowed (`ObjectModel.turned_anchor`, which an app that
  keeps objects inside a container overrides; the default leaves the anchor alone).
- `RotateObject.anchor` (default `None`): the place the object has after the turn, as plain data. A turn that moves
  the object is one command and one undo step; its inverse carries the old place. A command without one is stored as it
  always was, so no schema change: a log written before this reads unchanged.

## [0.26.0] - 2026-11-15

Pictures of files, shared by the converters of all three apps (D464).

### Added
- `picture_body`, `asset_of`, `keeps_proportions`, `blank_png`, `Rasterise`, `FILE_IMPORTER`, `IMAGE_STYLE`,
  `UNKNOWN_TIME`, `FALLBACK_SIDE`: how a picture of a docx, odt, pptx or odp file becomes the image object of the
  model (and a rendered text container the picture of a file), moved here from `claudia-creates-io` so that composes
  reads and writes pictures the same way creates does. The names `claudia_creates_io` exported stay there too.

## [0.25.0] - 2026-11-15

Named ranges are things (D552); replaying the history shows differences, and a step can be restored (D553).

### Added
- `Document.changes_since(rev, limit)` and `Changes` (D553): every place that changed after a step of the active line,
  each once, in the order it was first changed; the steps after `rev` are replayed once on a scratch model.
- `Document.restore_revision(rev, author)` (D553): go back to the state after any one step of the active line, by
  forking, as `restore_checkpoint` does. The first entry of the new line is the kernel's `Restore`, named by the step.
- `ObjectModel.rename_thing(ctx, id, name)` (D552): an app that keeps names with more than a plain field (computes
  rewrites the formulas that read a renamed sheet) overrides it; it returns the old name and the commands that undo the
  rest. The default calls `set_thing_name`.
- `check_thing_name(..., shared=)`, `name_holder(..., ignoring=)`, `check_name_free(..., ignoring=)`,
  `check_object(..., shared_names=)` and `insert_object(..., shared_names=)`: a thing may keep its own name, a kind of
  thing may be left out of a collision (a range is not a clash with its own sheet's id), and an old log keeps its rule.

### Changed
- `AddObject` is schema 5 and `RenameThing` schema 2: both carry `legacy_names`, set by the upcaster for what was
  written before named ranges shared the namespace, so an old document replays unchanged.
- `RenameThing.apply` returns a `Batch` when renaming a thing had to change more than its name (a sheet's formulas).

## [0.24.0] - 2026-11-15

Names of things (D550): every object, slide, sheet and chart tab has one name, unique in the document.

### Added
- `clean_name`, `name_key`, `name_problem`, `free_name`, `MAX_THING_NAME` (`claudia_core.names`): what a name is, when
  two are the same (cleaned and case-folded), and the first free "<label> <n>".
- `ObjectBody.name` (default `""`), `RenameThing` (`core.RenameThing`, an exact inverse) and the event `ThingRenamed`.
- `ObjectModel.named_things`, `unnamed_things`, `thing_name`, `set_thing_name`, `check_thing_name`, `check_name_free`,
  `name_holder` and `names_in_use`: an app that names more than its objects overrides the first four.
- `Document.peek_revision(rev)` and `Look` (D551): the state after one step of the history on any line, the step, and the
  regions it touched (read against the state before and after it), for replaying the history. Touches nothing live.
- `Document.last_seen(present)` and `ObjectModel.has_thing(id)` (D551): the last step of the line after which a state
  satisfied a test (one forward pass on a scratch model), e.g. the last moment a deleted thing was still there.

### Changed
- `AddObject` is schema 4: bodies carry `name`. The upcaster reads older bodies as unnamed.
- A body with a name is checked (tidy, 1 to 60 characters, not somebody else's) when an object is added or replaced.

## [0.23.0] - 2026-11-14

Search and replace in composes and creates (E9.28, E10.19): the texts of objects, replaced without re-attributing them.

### Added
- `replace_spans(paragraph, edits, author)`: a paragraph with some stretches replaced. The words around an edit keep
  their authors (and the style and alignment), whoever replaced is the author of what they put in.
- `object_texts(model, containers, sources)` and `ObjectText`: the words (`box`, `label`) and the description of the
  objects of some containers (slides, paragraphs), as a search sees them; `edit_object_text(model, id, source, edits,
  author)`: the command that stores edits in one of them (`SetParagraph` or `DescribeObject`).

## [0.22.0] - 2026-11-14

Imported documents (D438).

### Added
- `Import` (`core.Import`): the first entry of a document made from a file, carrying the state the import made, the
  file's name, format and SHA-256 and whether the file is kept. Nobody's undo step; `redacted()` is the entry itself.
- `DocumentModel.load_state(state)`: become, in place, what `restore(state)` builds. The default takes over the
  attributes of a restored model; a model whose parts point back at it overrides it.

## [0.21.0] - 2026-11-14

Rendered text containers (D390-D395), the same in every app.

### Added
- The object kind `rendered` (in `OBJECT_KINDS`) and `ObjectBody.rendered`, the id of the definition it shows.
- `RenderedDefinition` (text, type, settings, picture, renderer note) and `MAX_RENDERING_SOURCE`.
- Commands `DefineRendering`, `UpdateRendering`, `ForgetRendering` and the event `RenderingsChanged`.
- `ObjectModel` methods `define_rendering`, `replace_rendering`, `forget_rendering`, `users_of_rendering`,
  `renderings_to_data` and `picture_of(body)`, which every drawing and export asks for the picture of an object.
- `restore_objects(..., renderings=...)`.
- `decode_image(data, *, checked_drawing=False)`: for a drawing a renderer made, `<use>` with local references is kept.

### Changed
- `AddObject` is schema 3; an upcaster gives older bodies `rendered: null`. The SVG sanitiser keeps the `xlink`
  prefix, so that other programs follow the references of a typeset page.

## [0.20.0] - 2026-11-13

What a new document starts with is nobody's undo step (UX-33).

### Added
- `Setup` (`core.Setup`): a `Batch` of what a new document starts with, made once by the server when it creates the
  document. It is in the history under its maker's name, but it is never an undo step (`undoable` is `False`), and its
  redacted form is a `Setup` too.
- `DocumentModel.setup_commands(language)`: the commands of that setup, for an app to override (none by default).
  `language` is the language of the maker's interface, or `None`.

## [0.19.0] - 2026-11-13

What an object says to someone who cannot see it (BITV 1.1.1); the search engine moves out of the kernel (SEC-18).

### Removed
- **Breaking**: `Query`, `CompiledSearch`, `Match` and `SearchError` (the module `claudia_core.search`). They are in the
  new package claudia-search (`claudia_search`), which runs patterns on `regex` with a deadline: the kernel imports the
  standard library only (CONTRIBUTING, rule 6), and Python's `re` cannot be stopped (SEC-18).

### Added
- `StyleDef.number_format`: a style may name one of the app's number formats (computes, D378), inherited like its CSS
  and written into a style's data only when set. `StyleBook.number_format(id)` finds it along the parents;
  `StyleBook.set_number_format(id, format_id)` sets or clears it.
- `ObjectBody.description` (at most `MAX_ALT_CHARS` characters) and `ObjectBody.decorative`, the same in every app. A
  decorative object has no description. A picture that has no description of its own is described by the words it was
  imported with, so documents written before the fields existed keep what they said (`ObjectBody.from_data` still reads
  a body without the two fields).
- The command `DescribeObject(id, description, decorative=False)` (`core.DescribeObject`): one history step with its
  exact inverse; its redacted form keeps the flag and drops the words.

### Changed
- `AddObject` is schema 2 (the body has the two new fields); schema 1 data is brought up to date by a registered
  upcaster. A model's `state_schema` is raised by one in each app that holds objects, which retires cached snapshots only.
- **Breaking** (small): `ImageImport.from_data` accepts an empty `alt`. Whether a picture needs words is the object's
  business now; a picture that is neither described nor decorative is refused by the server's `add_image` and
  `describe_object`, not by the kernel, so that a redacted or imported history always replays.

## [0.18.0] - 2026-11-13

Lists (E9.21); search, the engine (E1.12, D281–D284).

### Added
- `ListItem(list, level)` and `Paragraph.item`: a paragraph may be an item of a list, at a level 0 to 8
  (`MAX_LIST_LEVEL`). It is written to plain data only when set, so a paragraph that is no item serialises exactly as
  before (creates and its text boxes notice nothing); `Paragraph.with_item`.
- `claudia_core.lists`: `ListDef(id, scheme, start, name)`, `ListBook` (with a `version` that counts its changes),
  `SCHEMES` (`bullets`, `numbers`; `Scheme` says how markers are drawn and how far levels are indented) and
  `numbering_labels(entries, lists)`, the one pure function that derives every item's `Label(marker, path)`.
- The commands `CreateList`, `ChangeList` and `RemoveList` (the undo of a create, refused while `list_in_use` says an
  item uses the list) and the event `ListsChanged`. A model that holds lists has a `lists` attribute (a `ListBook`).
- `claudia_core.search`: what a person wants to find, compiled to a pattern and run on plain texts, for all three apps.
  `Query.from_data(data)` reads a search in one of three modes (`text`: what is typed is what is found; `builder`:
  parts to find, each *what x how many*, optionally kept under a name, plus conditions on the whole text; `pattern`:
  her own pattern, a filter and a replacement) and checks everything a client could get wrong; `Query.compile(extra_parts)`
  makes a `CompiledSearch` (`matches`, `admits`, `left_out`, `replaced`, `pattern_text`) that returns `Match` spans.
  An app adds parts of its own through `extra_parts`. `SearchError` carries the message, the field and the
  character position of a mistake. The engine is Python's `re`; since that cannot be interrupted, a pattern that could
  backtrack without end (`(a+)+$`, `(a|aa)+$`) is refused before it runs, and patterns, parts and texts have size caps.

## [0.17.0] - 2026-11-13

Page setup and language for every app (D917).

### Added
- `claudia_core.page`: `PageSetup`, `PageSetupError` and `PAPERS`, moved here from `claudia_composes` unchanged, plus
  the paper `slide` (7.5 × 13.333 in, a 16:9 slide; `describe()` says "Slide size"). The margins error now speaks of
  the content rather than the text.
- `claudia_core.language`: `normalize_language` and `LanguageError`, moved here from `claudia_composes`, and the
  command `SetLanguage` (kind `core.SetLanguage`) with the event `LanguageChanged` (`{type: "language", language}`),
  for every model with a `language` attribute; on another model it raises `TypeError`. Every app's registry has it.

## [0.16.0] - 2026-11-12

Hyphenation (D912).

### Added
- `CSS_VERSION` 4: `hyphens` (`none`, `manual`, `auto`), a property of the paragraph facet: whether the words of a
  paragraph may be broken with a hyphen at the end of a line, only at a soft hyphen typed into them, or also where
  the language's patterns allow. Nothing to upcast: a style without it keeps the CSS default, `manual`.

## [0.15.0] - 2026-11-11

A throwaway copy of a document, for previewing what the AI proposes (E7.8, D263).

### Added
- `Document.scratch(at=None)`: a new `Document` that starts from the state now (or at the revision `at`, on any line),
  with a log of its own and no store. Commands run on it like on any document, with its own events, locks and undo; the
  live document, its log, the disk and everybody's undo steps never notice it, and it never sees what happens live
  afterwards. The current state is copied (cost: the size of the state, not the length of the history); an older
  revision costs a replay from the nearest cached snapshot, as `materialize` does. `KernelError` for a revision that
  does not exist.

## [0.14.0] - 2026-11-10

The styling-suite plan, steps 1.2 to 1.6: every styled thing reads its slots.

### Changed
- **Breaking:** `fits(kind, slot)` is true when the kind can hold every facet the slot reads (D316): a box slot
  takes a box style and a paragraph style (a bundle, D309, D311); a slot that reads nothing takes only its own kind.
- **Breaking:** an object's own style must fit its container's slot and its words' style the words' slot
  (`ObjectModel.check_object`, so `AddObject`, `SetObjectStyle` and `SetParagraphStyle`): a shape's style is an
  outline, its words a paragraph style.
- `ObjectModel.style_in_use` counts the style of an object's words too, so a style only a shape's label uses
  cannot be taken back.

### Added
- `object_styles(body)`: the styles an object uses, one per slot.
- `CSS_VERSION` 3: `vertical-align` (`top`, `middle`, `bottom`) and `white-space` (`normal`, `nowrap`,
  `pre-wrap`) in the Box facet, for the box of a cell (D307).
- `Slot.to_data()` carries `takes`: the kinds of style that fit the slot.

## [0.13.0] - 2026-11-10

Facets, kinds and slots: what a style property means and where a style can be put (D303-D305, D312, D315; the
styling-suite plan, step 1.1).

### Added
- `claudia_core.facets`: the four facets (`TEXT_FACET`, `PARAGRAPH_FACET`, `BOX_FACET`, `OUTLINE_FACET`, all in
  `FACETS`), each a `Facet(name, properties)`; `facet_of(prop)`; `FACET_PROPERTIES`. Every property of
  `ALLOWED_CSS` belongs to exactly one facet, and `ALLOWED_CSS` is now *derived* from them — the list of
  properties is unchanged, and `CSS_VERSION` stays 2.
- `KINDS`: the kinds of style and the facets each may hold — `paragraph` (text, paragraph and box), `box`,
  `outline` (D312). `check_kind(kind, properties)` refuses, in one sentence, every property outside the kind.
- `Slot(name, reads, kind)`, `SlotTable` and `SLOTS`: the slots of everything that can be styled today — a composes
  paragraph, a text box, a shape, an image, a diagram, a cell (D304, D311). `fits(kind, slot)`.
  `SlotTable.with_row(thing, slots)` adds a later kind of thing without touching anything else (D315);
  `SlotTable.to_data()` is the plain-data form a server will send.
- `StyleDef.kind` (default `"paragraph"`), in `to_data`, in `StyleBook.views` and so in `StylesChanged`.

### Changed
- **Breaking:** `StyleBook.add` and `StyleBook.set_css` (so `CreateStyle` and `ChangeStyle`) refuse a property that
  is not of the style's kind, and a style based on a style of another kind.
- **Breaking:** `StyleDef.from_data` requires `kind`. There is no upcast of documents or logs from before kinds
  existed (D308, until the first release).

## [0.12.0] - 2026-11-09

The style surface the menus in all three apps are built on (D203).

### Added
- `StyleBook.resolved(style_id, colours)`: one style's CSS with its parents taken in *and* its palette roles turned
  into literal colours. What `views` already returned per style, now askable for one — anything that paints or
  exports needs it, and reading `computed` instead silently dropped every colour that was a role, which is exactly
  what the pptx exporter was doing.

## [0.11.0] - 2026-11-08

A diagram joins the shared object layer as its own kind, so a chart can be a floating object on a slide, sheet
or paragraph the same way an image or a shape is (E6.6). What a diagram draws is deliberately opaque to the
kernel — the same split the object layer already draws between a body and an anchor, applied to a kind's own
content instead of its placement, since only computes (today) knows what a chart's range and titles mean.

### Added
- `claudia_core.objects`: `"diagram"` joins `OBJECT_KINDS`; `ObjectBody` gained a `diagram` field (the id of a
  definition, alongside its existing `shape`/`image`).
- `DiagramDefinition`: a `Protocol` for what a diagram draws, mirroring `Anchor` — an app reads its own back
  through the new `ObjectModel.diagram_from_data(data)` hook, the one door this data enters through.
- `ObjectModel.diagrams`, `define_diagram`, `forget_diagram`, `replace_diagram`, `users_of_diagram`, and
  `diagrams_to_data()`/the `diagrams` parameter of `restore_objects()` — the same shape as the existing
  shape/image methods, except a diagram can also be redefined in place (`replace_diagram`), since unlike a
  shape or an image, a diagram is meant to be edited after the fact.
- `DefineDiagram`, `UpdateDiagram` and `ForgetDiagram`: the commands behind the above, each with its exact
  inverse (mirroring `DefineShape`/`ForgetShape`).
- `DiagramsChanged`: the event a view hears when a diagram definition is added, edited or forgotten.

### Changed
- `AddObject.label`/`summary` and `shifted_by` now cover `"diagram"` alongside `"text"`/`"shape"`/`"image"`.

## [0.10.0] - 2026-11-08

The document's palette: colours named by what they mean (D200–D203). **Breaking:** `StyleBook.views` gained a
parameter and every style now travels with a third form of its CSS; a model that holds a style book is expected to
hold a palette beside it.

### Added
- `claudia_core.palette`: `ColourRole` (id, name, purpose, colour), `Palette` (an ordered, extensible mapping of
  them), `Reading` (how one role reads against another), `PaletteChanged`, and the commands `SetRole` and
  `ReplacePalette`, each with its exact inverse. Plus `builtin_palette()`, `BUILTIN_ROLES` (nine roles), `PAIRINGS`,
  `TEXT_FLOOR`, `UI_FLOOR`, `MAX_ROLES`, `contrast()` and `luminance()` (WCAG 2.2).
- `resolve_css(css, colours)`, `roles_used(css)` and `rgb_of(colour)` in `claudia_core.css`.
- `core.SetObjectStyle`: puts an object under another style of its own. An object's style was settled by
  `AddObject` and could never be changed again, which left a style menu with nothing to do.
- `claudia_core.styles.palette_colours(model)`: the role colours of a model that has a palette, asked of the model
  rather than imported, so that the two modules can still be used apart.

### Changed
- **Breaking:** `CSS_VERSION` is 2. A colour may now be a role of the palette — `@accent`, or `@accent/55` for that
  role at 55% opacity — wherever a colour is accepted, including inside a `border-*` shorthand. `@` is no longer
  refused outright in a value; every value check other than the colour one refuses it anyway, so a role can only
  land where a colour belongs. Nothing else about the allow-list changed: `url()`, `var()`, `calc()` and
  `!important` are still refused, which is what `resolve_css` exists to protect.
- **Breaking:** `StyleBook.views(colours=None)` now returns a `resolved` form of each style beside `computed`.
  `computed` still names the roles, which is what a style menu shows; `resolved` has the literal colours, which is
  what a client draws with. Without `colours`, a declaration naming a role is left out of `resolved`.
- Changing the palette emits `StylesChanged` as well as `PaletteChanged`: a client is deliberately unable to
  resolve a role itself, so the styles have to travel again.

## [0.9.0] - 2026-11-08

One shared object layer for shapes, images and text boxes, and an object's words as a paragraph (D177–D182). This
release was built but never written down; it is recorded here after the fact, with the versioning policy's own
rule in mind — the API changed, so it gets a version and an entry.

### Added
- `claudia_core.objects`: `ObjectBody`, `VisualObject[A]`, the `Anchor` protocol, `ObjectModel[A]`, `ObjectSet`,
  `ObjectsChanged`, `ImagesChanged`, `ShapesChanged`, `paragraph_for()`, and the whole `core.*` object command
  family — `DefineShape`, `ForgetShape`, `DefineImage`, `ForgetImage`, `AddObject`, `RemoveObject`, `MoveObject`,
  `ResizeObject`, `RotateObject`, `SetText`, `SetParagraph`, `SetParagraphStyle`, `SetSnap`.
- `claudia_core.paragraphs`: `Paragraph`, `Run` and the run arithmetic that used to be `claudia_composes.runs`, so
  that one paragraph entity serves a document, a text box and a shape's label alike.
- `claudia_core.shapes`: `ShapeDefinition`, `parse_shape`, `ShapeError`, `FORMAT`, `BOX` — the shape format only;
  reading a library off a disk stays in `claudia_creates`, because the kernel does no I/O.
- PNG among `SUPPORTED_IMAGE_FORMATS`, APNG included, with a still first frame taken without re-encoding.

### Changed
- **Breaking:** an object is a shared body plus a per-app anchor. `ObjectBody.text` became
  `ObjectBody.paragraph: Paragraph | None`, so an object carries two styles: its own (`fill`, `stroke`,
  `stroke-width`) and its paragraph's.
- **Breaking:** `ObjectSet` names a `container`, not a slide or a sheet.

## [0.8.0] - 2026-11-07

I18n groundwork (E5.7, D31, D148): the kernel gains stable error identity, without taking on gettext or any other
translation dependency itself.

### Added
- `KernelError.code` and a unique `code: ClassVar[str]` on every subclass (`unknown_command`, `schema_too_new`,
  `missing_upcaster`, `revision_mismatch`, `region_held`, `stale_edit`, `undo_refused`, `undo_conflict`,
  `redaction_error`, `replay_error`): a machine-readable identity for each error, independent of `str(exc)`'s
  baked English sentence. A future translator picks the message to show from `code`; the kernel itself still does
  not import gettext or know any catalog exists (`test_purity.py`).
- `MissingUpcaster` now also carries `self.kind` and `self.schema` (previously only in the message text).

Note for `scripts/api_surface.py`: it inspects callable signatures and `property` instances only, so a plain
`ClassVar` attribute like `code` does not show up in the snapshot diff on its own — the snapshot still needed
regenerating by hand for this release, same as any other addition.

## [0.7.0] - 2026-11-07

Images, shared by every app that can hold a picture (E10.8). This is the first piece of the image-import feature;
`claudia-creates` builds on it to let the **creates** app put an imported image on a slide. `claudia-composes` and
`claudia-computes` can reuse the same `ImageAsset`/`ImageImport`/`decode_image` for their own object kinds later,
without re-deciding what a decoded image or an import record looks like.

### Added
- `decode_image(data) -> ImageAsset`: a pure-Python, dependency-free decoder for JPEG, GIF, BMP and SVG
  (`SUPPORTED_IMAGE_FORMATS`). It reads only what is needed to find a pixel size — a JPEG's SOF marker, a BMP's
  `BITMAPINFOHEADER`, a GIF's logical screen descriptor and block structure, an SVG's `width`/`height` or `viewBox` —
  and never decodes a pixel. `MAX_IMAGE_BYTES` (8 MB) bounds a single asset.
- `ImageAsset`: a decoded image, identified by the sha256 of its bytes (so two imports of the same picture can share
  one asset once an app chooses to reuse it). For an animated GIF, `animated` is true and `first_frame` holds a
  complete, still GIF of just the first frame, so a view can show something before the person asks to play it.
- `ImageImport`: how one copy of an asset entered one document — `imported_by`, `imported_at`, `alt` (required: every
  imported image needs a short description), `source` (`"disk"` today; `"clipboard"` is a later addition), and
  `source_name`/`source_path`. `ImageImport.masked(viewer)` hides `source_path` from everyone but the importer,
  without hiding that the image came from disk or who imported it (the product decision that a colleague sees
  "imported from disk", not the importer's own filesystem path).
- `ImageError`: raised by `decode_image` and by `ImageAsset.from_data`/`ImageImport.from_data`, naming what is wrong.
- SVG is sanitized, not merely parsed: a `DOCTYPE` or `ENTITY` declaration is rejected outright at the text level
  (an entity-expansion bomb or an external-entity read starts with one, and the standard library's XML parser does
  not guard against either); `<script>`, `<foreignObject>`, `<iframe>`, `<use>` and the SMIL `<animate*>`/`<set>`
  elements are removed; event-handler attributes (`on*`) and any `href`/`xlink:href` that is not a same-document
  anchor (`#...`) are removed. The rest of the drawing survives.

### Fixed
- **`decode_image`'s `MAX_IMAGE_BYTES` cap was enforced on the live-import path only.** `ImageAsset.from_data` — the
  deserialization path used for command-log replay and for loading a document from storage — accepted a payload of
  any size, so a document whose command log already holds an oversized image (however it got there) would decode it
  anyway, including its `first_frame`. Fixed with a cheap pre-check on the base64 text length (so an oversized
  payload is rejected without decoding it) plus an exact check on the decoded length, applied to both `data` and
  `first_frame`.
- **A truncated GIF data sub-block miscounted frames instead of failing.** The block-structure walk did not check
  whether a length byte claimed more data than remained, so it could run past the end of the buffer and return a
  position the caller reads as "no more blocks" — a corrupted first frame of a genuinely animated GIF silently
  decoded as `animated=False` with only that frame, not an error. `ImageError` now, for a sub-block whose length
  runs past the end of the data.
- **The SVG sanitizer's `DOCTYPE`/`ENTITY` check only scanned the first 2048 bytes.** A `DOCTYPE`/`ENTITY`
  declaration pushed past that offset by padding earlier in the prolog (a long comment, say) is still well-formed
  XML and still reached the parser unredacted — an XXE/entity-expansion bypass, not merely an edge case. The check
  now scans the whole decoded text.

### Notes for implementers
- `ImageAsset.to_data()`/`from_data()` carry the image's bytes as base64 text, because a document's state and the
  server's wire protocol are both JSON (there is no binary attachment channel). A document with many or large
  images can approach the protocol's 16 MB message limit on a plain `snapshot` request; that is an accepted
  limitation of embedding images in the document state (there being no separate blob store yet, see the E2
  container format), not something this change solves.
- `ImageImport`'s redaction story is intentionally not addressed here: it is covered by the project's open decision
  on redaction in general, not decided as a side effect of adding images.

## [0.6.0] - 2026-11-06

Go back to a checkpoint, with everybody's consent (E3.7, D149): the live session needs a read-only preview of a line
before anybody is asked to switch to it.

### Added
- `Document.peek_line(line)`: the state of any line (active or hidden), rebuilt on a scratch model, without
  switching to it and without touching the live model, undo steps or checkpoints. `KernelError` for a name that is
  not a line of this document.

## [0.5.0] - 2026-11-03

Styles in the kernel (E1.10, D73, D75): one CSS allow-list and one style model for all three apps.

### Added
- `ALLOWED_CSS`, `CSS_VERSION` (1), `validate_css`, `parse_css`, `format_css`, `CssError`, `CssProblem`: the CSS a style
  may hold. A short list of properties and value types (font, size, weight, style, decoration, colours, alignment,
  line height, spacing, margins, padding, borders (`border-left` and the like: width, style, colour), and `fill`, `stroke`, `stroke-width` for shapes); nothing with `url()`, `var()`,
  `calc()`, `@`-rules or `!important`. `parse_css` reads the text of a style and reports every problem with its line
  and property.
- `StyleDef`, `StyleBook` (styles based on each other; stores only differences; `computed`, `chain`, `children`,
  unique names and ids, provisional names such as `Heading 1 (changed)`) and the event `StylesChanged`.
- Commands `CreateStyle`, `ChangeStyle`, `RenameStyle` and `RemoveStyle` (the undo of a creation). A model that wants
  styles has a `styles` attribute (a `StyleBook`) and may answer `style_in_use(style_id)`. A colleague's later change
  of the same property, a rename, or a style based on the new one makes an undo refused, never an overwrite.

## [0.4.0] - 2026-11-02

### Added
- `Command.summary`: a sentence for the history panel (`B3 = 40`); by default the label. It may name values, so it is
  not part of what survives a redaction. `Batch.summary` joins the first three of its commands.
- The `command` event carries `summary`.

## [0.3.0] - 2026-11-02

### Added
- `Document.execute(..., base=revision)`: an edit made against a view that is not on the active line is refused with
  the new `StaleEdit` (edits in flight during a restore or switch).
- `Document.switch_to(line, author)`: the way back after a restore. `Document.lines()` and `Line` list the lines.
  `Switch` (`core.Switch`) records the switch in the log.
- `CommandLog.on_path(rev, head)`.
- `__version__` and a curated `__all__`; the API surface is snapshotted by a test.

### Changed
- `BranchSwitched.fork_point` is now the last revision both lines share (it was the checkpoint's entry, which is the
  same thing for a restore).

### Removed
- Names that were only importable by accident (`claudia_core.clock` etc. as attributes of `__all__`).

## [0.2.0] - 2026-11-02

### Added
- `Document.execute` enforces locks (`RegionHeld`) for every author.
- Restoring a checkpoint forks (`restore-N` lines, `core.Restore`); `side_revisions`, `history_revisions`,
  `discard_side_history`. `CommandLog.active`, `fork`, `activate`, `discard_off_path`.
- `Command.shifted_by` and `UndoConflict`: collaborative undo refuses to overwrite a colleague's later work.

### Removed
- **Breaking:** `DocumentModel.diff_to` and restore-by-inverses.

## [0.1.0] - 2026-11-02

First draft of the kernel (E1.1-E1.9): command log, `Revision(branch, seq)`, per-author undo, regions and locks,
message classes, checkpoints, redaction, manifest.
