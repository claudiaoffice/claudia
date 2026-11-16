# Text structure across the three apps — the entities, where they live, what moves (plan)

**Status: plan of 2026-11-16, nothing built.** It widens `e9-composes-outline-references-toc.md` (the composes design
of the same day) to creates, and replaces that note's section 11 ("Where the code goes"). The class diagram is
`mockups/text-structure-architecture.svg`; it replaces `composes-toc-architecture.svg`. No decision numbers are taken.

**What it enables:** outline levels, numbered headings, lists, the numbering manager, references and the table of
contents in composes; numbered slide titles, lists that run across text boxes, references ("see slide 7") and an
agenda in creates; references in the text boxes of all three apps.

**The owner's input of 2026-11-16 that shapes it:**

- A presentation has a title text box on every slide that names the slide. Title boxes are linked across slides, e.g.
  so they move together.
- Numbering one title box numbers all of them. A list continues across text boxes as it continues across paragraphs
  in composes.
- A text box keeps **one paragraph** for now (D181 stands). Several paragraphs per box (bullets, PPTX/ODP body
  placeholders) is a later, separate decision; nothing below stands in its way.

## 1. The shape of it

Four layers, one rule per layer:

| Layer | What is in it | Rule |
|---|---|---|
| **Stored** | `StyleDef` (+ outline, + numbering), `SchemeBook`, `ListBook`, `Paragraph` (item, + fields, + generated) | Changed only by commands, in `claudia_core`, the same in every app |
| **The seam** | `ParagraphHost`: an app's paragraphs in reading order, and where each one is | The only part each app writes for itself |
| **Derived** | `TextStructure`: labels, shown fields, contents entries, targets, and the events that report changes | Worked out once, in `claudia_core`, for every app |
| **Drawn** | `layoutParagraph` (TypeScript) and one Vue component for the words of a paragraph | Every place that shows a paragraph uses them: editor, slide, thumbnail, presenter, print, PDF |

The two errors found on 2026-11-16 (two lists of heading names, one in Python and one in TypeScript; list markers in
the editor but not in print) are each a layer rule broken. The plan removes both by construction: a heading is a
stored property sent as data, and markers are drawn by the one function every view and print path calls.

This follows patterns the code already has: `claudia_core.object_texts` ("the app names the containers") with the
search hosts of each app; `claudia_server.search_methods` with `composes_search.py` and `creates_search.py`;
`ObjectModel`, which every app's model inherits beside `DocumentModel`.

## 2. The entities

### 2.1 Stored (in `claudia_core`)

| Entity | Module | New / changed / moved | Holds | Used by |
|---|---|---|---|---|
| `StyleDef` | `styles.py` | changed | + `outline: int \| None` (1–9), + `numbering: str \| None` (a list id); both inherited along `based_on` | all three |
| `StyleBook` | `styles.py` | changed | + `version`, + `outline_of(style)` | all three |
| `SetStyleOutline` | `styles.py` | new command | style, outline, numbering; exact inverse | all three |
| `Scheme`, `LevelFormat` | `schemes.py` (from `lists.py`) | **moved and changed** | nine level formats: format, bullet, before, after, from_level; indent, gap | all three |
| `SchemeBook` | `schemes.py` | new | the document's schemes; built-ins `bullets`, `numbers`, `chapters`; `version` | all three |
| `CreateScheme`, `ChangeScheme`, `RemoveScheme` | `schemes.py` | new commands | | all three |
| `ListDef`, `ListBook`, `ListItem`, list commands | `lists.py` | unchanged | | all three (already core) |
| `Paragraph` | `paragraphs.py` | changed | id, style, text, runs, item, + `fields`, + `generated` | all three |
| `Field`, `FieldRegistry`, `RefField` | `fields.py` | new | target thing id, what to show; helpers to count, split and strip U+FFFC | all three |
| `Generated`, `Toc` | `generated.py` | new | `Toc`: levels, numbers, pages, leader | composes (table of contents), creates (agenda) |
| `SetListItem` | `lists.py` (from `claudia_composes.commands`) | **moved** | paragraph id, item; works on any paragraph, a body paragraph or an object's | all three |
| `SetField`, `SetGenerated` | `fields.py`, `generated.py` | new commands | paragraph id, index or generated | all three |

**Why a `Toc` lives in core and not in composes:** a creates agenda is the same thing. It is a generated paragraph
in a text box, listing the slides' titles with slide numbers.

### 2.2 The seam (in `claudia_core`, `structure.py`)

```python
class Placed(NamedTuple):
    paragraph: Paragraph
    container: str            # the paragraph's body or the object's slide, sheet or anchoring paragraph
    main: bool                # part of the main text (counts for the outline and the contents) or an aside
    place: str | None         # where a reader finds it, if the kernel knows: "7" (slide 7); None = ask the layout

class ParagraphHost(Protocol):
    styles: StyleBook
    lists: ListBook
    schemes: SchemeBook
    def reading_order(self) -> Iterator[Placed]: ...       # every paragraph, in the order it is read
    def paragraph(self, paragraph_id: str) -> Paragraph: ...
    def put_paragraph(self, paragraph: Paragraph) -> None: ...
    def thing(self, thing_id: str) -> Thing | None: ...    # a target that is not a paragraph (a slide, a picture)
    structure_version: int                                 # bumps when the reading order or a paragraph changes
```

What each app brings:

| App | `reading_order()` | `main` | `place` |
|---|---|---|---|
| composes | the body's paragraphs in order, each followed by the paragraphs of the objects that hang from it (in stacking order) | body paragraphs | `None`: the page comes from the layout |
| creates | slides in order; on each slide the paragraphs of its objects in **stacking order, bottom first** (what PowerPoint reads to a screen reader, so a PPTX keeps its order) | every object paragraph | the slide number, known in the kernel |
| computes | sheets in order; on each sheet its objects' paragraphs in stacking order. Cells are not paragraphs and stay out | none (no outline in a workbook) | the sheet's name |

Paragraph ids are unique across a document. Composes body paragraphs are `b<n>`. An object's paragraph has the
object's own id, `o<hex>` (`paragraph_for`). Slides are `s<n>`. So one map keyed by paragraph id serves both the body
and the objects; a test guards it.

### 2.3 Derived (in `claudia_core`, `structure.py`)

`TextStructure(host)` is one object per document, owned by the model (as `TextModel` owns its label cache today). It
works out, caches, and diffs against what the clients were told:

| Method | Answers | Cache key |
|---|---|---|
| `effective_item(p)` | the paragraph's own `item`, else `(style.numbering, style.outline − 1)` | — |
| `labels()` | `Label` (marker, path, + number) per paragraph id | structure, styles, lists, schemes versions |
| `outline()` | (paragraph id, level, number, text) of every `main` paragraph with an outline level | the same + text of outline paragraphs |
| `shown()` | the text and state of every field | the same + a reverse index target → fields |
| `entries(paragraph)` | the entries of a generated paragraph (`Toc`) | as `outline()` |
| `targets(query)` | what the reference picker lists | not cached |
| `settle(ctx)` | emits `LabelsChanged`, `FieldsChanged`, `GeneratedChanged` for what differs | — |

The events move to `claudia_core.events` with the same wire `type`s (`labels`, `fields`, `generated`), so the web
client hears them the same way from every app.

### 2.4 Drawn (TypeScript)

| Piece | Where | Change |
|---|---|---|
| `layoutParagraph` | `layout/src/text/paragraph.ts` | takes `label` (a hanging marker) and `fields` (shown text, or a page to fill in); the one function composes, creates and the object layer already call |
| style data sent to the layout | `TextStyle` in `apps/composes.ts`, `apps/creates.ts` | + `outline`; `headingLike` and `KEEP` go, keep-with-next reads `outline` |
| `layout/src/text/entry.ts` | new | an entry line: number, text, leader, page column (contents and agenda) |
| page passes | `apps/composes.ts` | at most three, for page fields and the contents (creates needs none: its places are slide numbers) |
| `ParagraphWords.vue` | `web/app/components`, new | draws one paragraph's words: marker, text, field atoms, search marks; replaces every place that draws an object's words (below) |
| `ParagraphEditor.vue` | new, from `TextEditor.vue`'s paragraph editing | one paragraph, editable, with atoms; replaces creates' `<textarea>` |
| `lib/paragraph-pieces.ts` | new, from `piecesOf` | one function that splits a paragraph into pieces: marker, text, field, found |

## 3. What moves, what is replaced, and why

| Today | Becomes | Why |
|---|---|---|
| `HEADING_STYLES` in `claudia_composes/model.py` and `KEEP` / `headingLike` in `layout/src/apps/composes.ts` | `StyleDef.outline`, sent as style data | One fact, stored once; any style can be a heading, in any app |
| `SCHEMES` constant in `claudia_core/lists.py` | `SchemeBook` in the document (`schemes.py`) | Editable in the numbering manager; the same look on every server (D200's reasoning) |
| `TextModel.labels()`, `_labels`, `_told`, the diff in `settle` (composes) | `TextStructure` in core; `TextModel` keeps one and implements `ParagraphHost` | creates needs exactly the same logic; written twice, it would drift |
| `LabelsChanged`, `ItemChanged` in `claudia_composes/events.py` | `claudia_core/events.py`, same wire form | Every app emits them |
| `composes.SetListItem` | `core.SetListItem` on any paragraph; the old kind stays readable as an alias so stored histories replay | Lists across text boxes in creates. Pre-release, but the demo's documents still replay |
| My earlier `claudia_composes/references.py` and `contents.py` | `claudia_core/fields.py`, `generated.py`, `structure.py` | creates' references and agenda |
| Server: `composes_lists.py` (`make_list`, `indent_item`, …) | `structure_methods.py` (shared: lists, schemes, Number Headings, outline, references, contents) plus a thin host adapter per app, as `search_methods.py` is | One set of wire methods for all apps; the one-server pivot (D620–D639) makes a shared module natural anyway |
| creates: object words edited in a `<textarea>`, saved whole by `set_text` (`SlideCanvas.vue`, `slide-session.ts`) | `ParagraphEditor.vue`, saving characters through the core text commands (3.1) | A textarea cannot hold a reference atom, and whole-text saving attributes every word to the last person to save |
| Object words drawn separately in `SlideCanvas.vue`, `SlideView.vue` and `PresentShow.vue` (each through `wordsOf`/`piecesOf`), with composes' floating objects (E9.29) and computes' object layer about to add more | `ParagraphWords.vue` | Every copy would need markers, atoms and search marks; this is the kind of drift that left print without markers |
| `block_kind` "heading" by name (D554) | by outline level | Follows from the first row |

**What stays:** D181 (one paragraph per object), `ListBook` and the list commands (already core), `TextCommand` and
anchor following in composes, `SplitBlock`/`JoinBlocks`/`SetStyle` (body-only), the object layer, things and names
(D550, D554), `SetText` for whole replacements (search and replace, the AI) — made to keep fields (3.1).

### 3.1 Text commands on object paragraphs

Today composes types character by character (`composes.InsertText`/`DeleteText`), while objects get their words
replaced whole (`core.SetText`). For atoms and fair authorship, object paragraphs need the character-level commands
too. Plan:

- Move the paragraph-level part of `InsertText`/`DeleteText` into `claudia_core` as `core.InsertText` /
  `core.DeleteText` on any paragraph id, with `fields` (schema 3). Composes keeps its follow-up behaviour (anchors,
  suggestions) through a hook the host implements; its old kinds stay readable as aliases.
- `core.SetText` / `SetParagraph` keep the fields of the U+FFFC they do not touch (`replace_spans` already keeps
  authorship that way); a replacement that would cut a U+FFFC removes its field, and the inverse puts it back.

This is the biggest single move. It can come after numbered titles and lists in creates, which need only
`SetListItem` and the style commands (section 5).

## 4. Linked title boxes

A link across slides is its own entity. It belongs to the alignment work the owner asked mock-ups for on 2026-11-16,
and is not needed for numbering:

```
ObjectLink   id, members: tuple[object id, ...], shares: {"geometry", "style"}     # claudia_core/objects.py
```

- **Numbering does not depend on it:** it lives on the style. Every box in the style "Slide Title" is numbered as
  soon as that style points at a list.
- **What the link adds:** its members keep one style, so a link cannot hold some numbered and some unnumbered titles.
  Moving one member moves all of them.
- **The menu:** Format ▸ List ▸ Numbered List on a box whose style has an outline level is offered as **"Number All
  Slide Titles"**: it changes the style, exactly as Number Headings does in composes. On a box without an outline
  level it makes that one box an item, and the list continues in the next box in reading order, across slides.

New in creates' built-in styles: **Slide Title** (outline 1), with Heading 2 to Heading 6 shared with composes (one
set of built-in outline styles, `claudia_core.styles.outline_styles()`, so the two apps cannot disagree about them
either). Today creates has no title style at all. PPTX/ODP import maps `type="title"` and `ctrTitle` placeholders to
it.

## 5. Order of work

| Step | What | Apps | Depends on |
|---|---|---|---|
| **A** | Drawing first: `layoutParagraph` takes a label; `ParagraphWords.vue` replaces the three copies in creates and is what E9.29 and computes use; markers in print and PDF | all | — |
| **B** | Outline level on styles; built-in outline styles shared; Slide Title in creates; `headingLike`/`KEEP`/`HEADING_STYLES` go | all | — |
| **C** | `ParagraphHost`, `TextStructure`, events to core; composes moves onto it with no visible change; creates implements the host | composes, creates | A, B |
| **D** | `SchemeBook`, `chapters`, style numbering, Number Headings / Number All Slide Titles, the numbering manager; `core.SetListItem`, lists across text boxes | composes, creates | C |
| **E** | `Generated`/`Toc`: composes table of contents (flow view), creates agenda (slide numbers from the kernel) | composes, creates | D |
| **F** | Composes page passes: page numbers in the contents, print and PDF | composes | E |
| **G** | Core text commands for any paragraph; `ParagraphEditor.vue` replaces the textarea | creates (composes floating objects, computes text boxes for free) | C |
| **H** | Fields and references; the picker; atoms in both editors | all | C, G |
| **I** | Page and slide references ("see page 12", "see slide 7") | composes, creates | F, H |

Steps A and B also remove the two errors found today, so they come first even before the visible features.

## 6. Tests that keep the layers honest

Written first, as part of the steps above:

- **No second list of style ids.** A test fails if `layout/src` or `web/app` contains a built-in style id as a literal
  (`heading-1`, `title`, `slide-title`, …). Whatever the layout needs about a style comes as data.
- **One sample document, every surface.** One fixture per app with lists, numbered headings or titles, a reference and
  a contents or agenda. A test checks that the editor's pieces (`paragraph-pieces.ts`) and the layout's display list
  carry the same markers and the same field texts. Today's missing print markers would have failed it.
- **Same answer in every app.** The `TextStructure` tests run against a composes host and a creates host built from
  the same paragraphs, and must give the same labels.
- **Ids.** Paragraph ids are unique across body and objects; a field's U+FFFC count equals its tuple's length after
  every command (a property test).

## 7. Open points (with the default taken here)

1. **Reading order in creates:** stacking order (default, as PowerPoint), or a stored order apart from stacking
   (later, with a Reading order panel, if users need to layer and read in different orders).
2. **Floating objects in composes:** their paragraphs count in lists (default) but not in the outline or the contents.
3. **Old command kinds** (`composes.SetListItem`, `composes.InsertText`, `composes.DeleteText`): read as aliases
   (default) or dropped, given the pre-release stance.
4. **Agenda content:** the titles of all slides (default), or only titles of a chosen outline level (sections).
5. **computes:** references in its text boxes come with step H at no extra cost; lists in text boxes on a sheet
   too. The List menu stays off for cells ("Cells hold no lists").
6. **Several paragraphs per text box:** a separate decision, mainly for bullets and PPTX/ODP import. With the host
   design it changes only creates' `reading_order()` and the object's body; nothing in `TextStructure`.
