# claudia composes — outline levels, numbered headings, references and the table of contents (design)

**Status: proposal of 2026-11-16, nothing built.** Widened the same day to creates and computes by
`text-structure-across-apps.md`, which decides where the code goes (it replaces section 11 below) and the order of work
(its steps A–I replace the slices S0–S6 of section 12; the tests listed there still apply). The owner agreed the direction on 2026-11-16 (section 1). Screens
and class diagram are in `mockups/`, to be agreed before any UI code (project rule):

| Sheet | Shows |
|---|---|
| `text-structure-architecture.svg` | Where each part lives in the code base, for all three apps (see `text-structure-across-apps.md`) |
| `composes-numbered-headings.svg` | Numbered headings in the text, Format ▸ List ▸, the style editor's Outline section, the All numbering dialog |
| `composes-references.svg` | Insert ▸ Cross-Reference…, the target picker, a reference in the text (states, menu, keys) |
| `composes-table-of-contents.svg` | The table of contents in flow view and on the page, its options, how pages are found |

**No decision numbers are taken.** Ask the owner for a block in `decision-log/ranges.md`, then turn section 9 into
decisions. Stories: E9.22 (now narrowed to outline levels, numbered headings and the numbering manager), E9.30
(references in the text), E9.31 (table of contents). This note continues section 4 of `e9-composes-lists.md`.

## 0. The branch

`lists-and-anchors-in-compose` holds one commit, `a3f0669` ("Lists and anchors in compose, first version"). The owner
applied it to main as `95aa812` on 2026-11-13, and main has 89 commits more since. Checked file by file and symbol by
symbol (`SetListItem`, `make_list`, `indent_item`, `continue_list`, `list_start`, `LabelsChanged`, `data-marker`):
**the branch carries nothing main lacks**; main even has the native `format.list.*` actions the branch left open. A
merge of main into the branch would only produce conflicts between two copies of the same work. The update is therefore
to move the branch to main:

```sh
git branch -f lists-and-anchors-in-compose main     # or: git checkout lists-and-anchors-in-compose && git reset --hard main
```

This note and its mock-ups are a patch against `4b608aa` (main of 2026-11-15), i.e. against the updated branch.

## 1. What was asked and agreed

The owner wants tables of contents in composes. On the way: numbered headings, and references in the text ("see
chapter 2.3") whose number follows the structure. Agreed on 2026-11-16, in this order of work:

1. **An outline level is a property of a style**, not hard-coded heading names.
2. **Numbered headings**: a style names its numbering, so "Heading 1 is numbered" is one switch (E9.22, D306).
3. **The table of contents is a generated block** that stores only its settings; its entries are derived, never stored
   as paragraphs, so there is no "update field" step. Page numbers come from the layout.
4. **References in the text** are one general inline field that stores the target's id and what to show. The same
   field later carries citations (E9.16) and page fields (E9.14).

Also agreed: Heading 3 to Heading 6 become built-in styles; a table of contents is exported **without page numbers and
flagged for update** (the server has no layout); the work happens on `lists-and-anchors-in-compose`.

## 2. What the code has today (at `4b608aa`)

- **"Heading" is a list of names, twice.** `HEADING_STYLES = {"title", "heading-1", "heading-2"}` in
  `claudia_composes/model.py` decides `block_kind` (D554); `KEEP = {title, heading-1, heading-2, heading-3, subtitle}`
  in `layout/src/apps/composes.ts` decides keep-with-next. The two already disagree, and a style a person makes is a
  heading only if it is *based on* one of them.
- **Labels are lists only.** `TextModel.labels()` runs `numbering_labels` over the paragraphs' own `ListItem`s, cached
  on (structure counter, `ListBook.version`); `settle` emits `LabelsChanged`. `StyleBook` has **no version counter**.
- **Schemes are code.** `claudia_core.lists.SCHEMES` has `bullets` and `numbers`; a scheme's markers are fixed per level
  (`1.` `a.` `i.`), and a label's `path` is a tuple of counters with no way to print "2.3".
- **The print layout draws no list markers.** `TextBlock` in `layout/src/apps/composes.ts` is `{id, style, text}`: the
  web editor draws bullets and numbers (CSS `::before`), the print preview and its PDF do not. This is a gap today,
  independent of this work, and numbered headings would inherit it.
- **A paragraph holds characters only.** `Paragraph` is `id, style, text, runs, item`; nothing inline can point at
  anything.
- **Things and names exist.** Objects, slides, sheets, chart tabs (D550) and paragraphs (D554) are things with ids that
  are never reused and optional names in one namespace; a chat tag stores the id and shows the current name (D551).
- **Pages exist only in the client.** Pagination runs in the browser (D901); page numbers are `n / N` drawn by
  `pageNumberItems`; the Python exporters cannot know a page.

## 3. Outline level (E9.22, slice S1)

`StyleDef` gets one field, `outline: int | None` (1–9), inherited along `based_on` like `number_format`. A paragraph is
a heading of level *n* when its computed style has `outline = n`. That single fact feeds `block_kind`, the layout's
keep-with-next, the table of contents, numbered headings, the outline view (E9.12), the editor's `role="heading"` /
`aria-level` (a real BITV gain: screen-reader users can jump by heading) and the exporters (`text:outline-level` in
ODF, `w:outlineLvl` in docx). `HEADING_STYLES` and `KEEP` go away.

- **Built-ins:** Title has no outline level (it names the document, so the table of contents leaves it out, as Word
  and LibreOffice do); Heading 1–6 have 1–6. Heading 3–6 are new styles: serif, falling sizes (12.5, 11.5, 11 pt bold,
  11 pt italic), the same margins pattern as Heading 1 and 2.
- **Command:** `core.SetStyleOutline(style, outline, numbering)` with its exact inverse; refused for styles whose kind
  is not `paragraph`. It is a style change like `ChangeStyle` (same rights, same locks, one step in the history). The
  style editor gets an **Outline** section (mock-up `composes-numbered-headings.svg`, B).
- **`StyleBook.version`**, counted like `ListBook.version`, so the label cache can key on styles too.
- **Documents from before** (state schema ≤ 11) read a style without `outline` as none, except the built-in ids
  `heading-1` and `heading-2`, which get 1 and 2, so that D554's headings stay headings. A pre-release upcast of two
  ids, not a guess (open point 1).

## 4. Numbering schemes and numbered headings (E9.22, slice S2)

### 4.1 Schemes become document data

Today a scheme is code. The numbering manager needs to edit one, and a document must look the same on every server,
so schemes move into the document as a `SchemeBook` (like `StyleBook`, D200's reasoning for the palette):

```
Scheme       id, name, kind ("bullet" | "number"), levels: tuple[LevelFormat, ...]  (9), indent, gap
LevelFormat  format: "decimal" | "lower-alpha" | "upper-alpha" | "lower-roman" | "upper-roman" | "bullet" | "none"
             bullet: str            (for kind bullet)
             before: str, after: str  ("Chapter ", ".")
             from_level: int        which levels the label shows: 0 = the whole trail "2.3.1", n = from level n on
```

- **Built-ins** are seeded into every new document and on replay, as built-in styles are: `bullets` (• ◦ ▪),
  `numbers` (`1.` `a.` `i.`, as now) and a new **`chapters`** (`1` `1.1` `1.1.1` …, decimal, `from_level` 0, no
  trailing full stop, the DIN 5008 habit). A person may change a built-in; "Reset" puts it back.
- **Commands:** `core.CreateScheme`, `core.ChangeScheme`, `core.RemoveScheme` (refused while a list uses it), event
  `SchemesChanged`. `ListDef.scheme` keeps naming a scheme by id, so existing lists are untouched.
- **`Label` gains `number: str | None`**: the trail as a reference prints it, without `before`/`after`. For a chapter
  heading it is "2.3"; for item b under step 2 of a numbered list it is "2.b" (the full context, so "see step 2.b" is
  never ambiguous). `marker` stays what is drawn.
- `numbering_labels` keeps its signature and takes the scheme book; the counting rules of E9.21 are unchanged.

### 4.2 A heading style points at a list

`StyleDef` gets a second field, `numbering: str | None`: the id of a **list** (`ListDef`), not of a scheme. A paragraph
then has an *effective item*: its own `item` if it has one, otherwise `(style.numbering, style.outline − 1)` when both
are set. `TextModel.labels()` feeds effective items to `numbering_labels` and keys its cache on (structure,
`lists.version`, `styles.version`, `schemes.version`).

Why a list and not a scheme:

- **All heading styles that point at the same list count together**, as one outline: Heading 1 → level 0, Heading 2 →
  level 1, so 2, 2.1, 2.2, 3, 3.1. A second sequence ("Appendix A, A.1") is a second list with its own scheme, pointed
  at by an "Appendix" style with outline level 1.
- **Start at and continue already exist** for lists (E9.21), so "start chapters at 0" needs nothing new.
- **It is what the formats have.** docx links numbering to a style (`w:numPr` in the style's `w:pPr`, the `w:lvl` naming
  `w:pStyle`); ODF's `text:outline-style` is one such list for the outline. Import and export map one to one.

**Format ▸ List ▸ Number Headings** is one history step: create the list `outline` with scheme `chapters` if it is not
there, then `SetStyleOutline(…, numbering="outline")` for every style that has an outline level and no numbering yet.
Unticking takes `numbering` off those styles again; the list stays (it is cheap and keeps its start). A paragraph's own
`item` wins over its style's (a heading explicitly made a list item stays one) — open point 2.

### 4.3 The numbering manager

Format ▸ List ▸ **All Numbering…** opens a dialog shaped like All styles (list left, editor right; D302): the schemes
with a preview, per level its format, text before and after, which levels it shows, indent and gap; below, **Used
by** names the lists and styles that use the scheme, each a link that selects it. It edits the `SchemeBook`; every
change is one step. Screens: `composes-numbered-headings.svg`, C.

## 5. Targets (E9.30)

A reference points at a **thing** (D550, D554): a paragraph id, or an object id. This round adds no new kind of anchor.
Every paragraph already is one, its id is never reused, and a paragraph joined away hands its objects to the survivor
(the reference does not: it becomes broken, and undo of the join mends it). A bookmark inside a paragraph (a word), and
numbered captions ("Figure 4") are later; because the field stores a thing id, they slot in without a change to it.

A target does not need a name: the field holds the id, so pointing at an unnamed paragraph names nothing (unlike a
chat tag, which shows the name and therefore asks for one). The picker lists, for the whole document (the chat's `#`
list is limited to the view; this one is not): **headings** as an outline with their numbers, **numbered items**,
**named paragraphs** and **named objects**, with search. Server method `reference_targets(query?)` answers
`[{id, kind, level, number, text, name}]`.

## 6. Inline fields and references (E9.30, slice S5)

### 6.1 One mechanism: a placeholder character and a tuple

`Paragraph` gets `fields: tuple[Field, ...]`. Every field sits at one **U+FFFC** (OBJECT REPLACEMENT CHARACTER) in
`text`; the *k*-th U+FFFC is `fields[k]`.

Why this and not offsets: a field then needs no following at all. Cursors, zones, suggestions, objects' anchors,
authorship runs and locks already treat it as one ordinary character (`TextCommand.follow` is unchanged); insert and
delete only have to carry the fields of the U+FFFC they insert or remove; split and join partition and concatenate the
tuple by counting U+FFFC before the offset. Input from clients, paste and import has U+FFFC removed, so a field can only
be made by the command that makes one.

`claudia_core.fields` holds a registry of field kinds (as `CommandRegistry` holds commands), so that E9.16 registers
`cite` and E9.14 registers `page`/`pages` without touching this code. The first kind:

```
RefField  kind "ref"   target: str (thing id)   show: "number" | "text" | "number-text" | "page" | "name"
```

Default `show` by target: a numbered heading or item → `number`; an unnumbered heading → `text`; an object → `name`.

### 6.2 Commands

| Command | Change | Inverse |
|---|---|---|
| `InsertText(block, offset, text, by, fields)` | schema 3: `fields` for the U+FFFC in `text` | `DeleteText` |
| `DeleteText(block, offset, length)` | unchanged; `model.remove` also returns the fields cut | `InsertText` with those fields |
| `SetField(block, index, field)` | new: "show as" | `SetField` with the old field |

`redacted()` replaces every character but U+FFFC and keeps the fields: a field holds an id, not words, and the count
of U+FFFC must stay equal to the length of the tuple.

### 6.3 What a reference shows is derived in the kernel

`claudia_composes.references.resolve(field, model) -> Shown(text, state)`, `state` being `ok`, `broken` (the target is
gone) or `page` (the page is the layout's business, 6.5). `TextModel` keeps the shown values cached and a reverse index
target → fields, so typing in a heading re-resolves only the references to that heading, and a structural change (a
renumbering) re-resolves all of them once. `settle` emits `FieldsChanged((block, index, text, state), …)` like
`LabelsChanged`; the `blocks` answer carries each paragraph's shown fields. The words of a reference ("see chapter")
are typed by the author; the field shows only the number, text, name or page, so no interface language ends up in the
document.

### 6.4 In the editor

- The U+FFFC is drawn as an atom: `<span contenteditable="false" data-field data-thing="…">2.3</span>` with a quiet iris
  underline; the caret steps over it as one character. Backspace next to it selects it first; a second Backspace
  deletes it (the usual two-step for atoms, so a reference is not lost by accident).
- **Ctrl+click** or **Ctrl+Alt+Enter** goes to the target (centred, briefly tinted, with the Back chip of D551).
- A context menu: Show As ▸ (Number, Text, Number and Text, Page, Name), Go to Target, Remove Reference.
- **Broken:** dashed rose underline, ⚠ and "missing reference" (in the reader's language: it is interface, not
  content). Going to it replays the history to the last moment the target existed, as a broken chat tag does (D551).
- `aria-label` "Reference to heading 2.3, Results"; a broken one says so.

### 6.5 Pages and the layout (slice S4)

`page` is resolved by the layout, in the client, in two passes:

1. Lay out with every page reference at the width of the placeholder "000" in its font, and every table-of-contents
   entry with a page column of fixed width (the widest page number the document can have, measured once). Record the
   page on which each target paragraph starts (`paginate` knows it).
2. Fill in the numbers. The table of contents cannot reflow (its column is fixed); a paragraph with page references
   is laid out again; if the pagination moves, a third pass. Never more than three, so the result stays deterministic
   (D901); an unsettled third pass is reported as a note, as missing hyphenation patterns are.

In flow view (no pages) a page reference shows a muted "#" with the tooltip "The page is known in page view and
when printing".

## 7. The table of contents (E9.31, slices S3 and S4)

### 7.1 A generated paragraph

`Paragraph` gets `generated: Generated | None`. A generated paragraph has empty text and no runs; the server refuses
typing into it and splitting or joining into it, and Enter before or after it works as usual. Keeping it a paragraph
keeps everything that assumes a flat list of paragraphs (ids, `follow`, cursors, `BlockAnchor`, search, locks)
working, and makes it a thing (kind `contents`) that can be tagged and referenced.

```
Toc(Generated)  kind "toc"   levels: (first, last) = (1, 3)   numbers: bool = True   pages: bool = True
                             leader: "dots" | "none" = "dots"
```

Later, the reference list of E9.16 and lists of figures are other `Generated` kinds; a creates agenda slide could be
one too.

- **Insert ▸ Table of Contents** puts two paragraphs at the caret in one step: a "Contents" paragraph in the new style
  **Contents Title** (no outline level, so it does not list itself; its words are the author's to change) and the
  generated paragraph. On a table of contents the same entry opens its options.
- **Commands:** `SetGenerated(block, generated | None)` with its inverse; the paragraphs themselves come from
  `SplitBlock`/`JoinBlocks`.
- **Entries are derived:** `toc_entries(model, toc) -> tuple[Entry(target, level, number, text)]`: every paragraph
  whose outline level is in range, in document order, generated paragraphs skipped. Cached like labels, and typing in a
  heading only touches its own entry. `GeneratedChanged(block, entries)` tells the clients.
- **The look is styles (D306):** new built-in styles **Contents 1** to **Contents 9** ("an entry of the table of
  contents at level n"), restyled like any other. No look is stored in the `Toc`.

### 7.2 Where it is seen

- **Flow view:** the entries as links (`role="link"`), indented by level, number and text, **no page numbers**; a quiet
  chip on hover or focus, "Table of contents · levels 1–3 · Options…". Clicking an entry goes to the heading.
- **Page view and print:** number, text, dot leader, page number right-aligned; in the PDF each entry is a link, and the
  outline levels also become the PDF's bookmarks (both later in S4, they help BITV/PDF-UA).
- **Options popover:** levels from/to, numbers, page numbers, leader; a line "Looks: Contents 1–3 · Edit styles…".

## 8. Menus, keys, shells, strings

| Entry | Key | App |
|---|---|---|
| Insert ▸ Cross-Reference… | Ctrl+F2 | composes; in computes and creates shown, disabled, with the reason (the List precedent of E9.21) |
| Insert ▸ Table of Contents (on one: its options) | Ctrl+Shift+Alt+I | composes |
| Format ▸ List ▸ Number Headings (ticked when on) | Ctrl+Shift+Alt+H | composes; the List flyout is in every app (E9.21) |
| Format ▸ List ▸ All Numbering… | Ctrl+Shift+Alt+E | composes first; the dialog is shared code |
| Go to Target (on a reference) | Ctrl+Alt+Enter, Ctrl+click | composes |

The keys were checked against `web/app/lib/keys.generated.ts` at `4b608aa`: none is taken; they avoid Ctrl+Alt + a
letter (AltGr on German layouts, and the Ctrl+Alt letters are nearly all used), Ctrl+Alt+L/T (Ubuntu), Alt+F2 (GNOME's
run dialog) and F12 (the browsers' developer tools). Ctrl+F2 is LibreOffice's Fields key. The actions go into the
shared manifest (`clients/linux/src/claudia_shell_gtk/manifest.py`), from which `keys.generated.ts` and the Windows
and macOS menus are generated (D360, D361). Every new string goes into `po/claudia.pot` (D320): menu entries, the
dialog, the picker, "missing reference", the tooltips.

## 9. Import and export

| Format | Outline and numbering | References | Table of contents |
|---|---|---|---|
| ODT | `text:h` with `text:outline-level`; a list used by heading styles as `text:outline-style` when it is the only one, else a list style named in the paragraph styles | `text:bookmark` at the target (named by the thing's name or id), `text:bookmark-ref` with `text:reference-format` (`number`, `text`, `number-all-superior`, `page`) and the shown text as content | `text:table-of-content` with its `text:table-of-content-source` (levels) and an `text:index-body` of the entries **without page numbers**; ODF has no "update on open" flag, so the export dialog lists the loss `toc-pages` (D452) |
| docx | `w:outlineLvl` in the style; numbering linked to the style through `w:numPr` in the style's `w:pPr` | `w:bookmarkStart/End` named `_Ref…` at the target; `REF _Ref… \r \h` (number), `\h` (text), `PAGEREF` (page), with the shown text as the cached result | `w:sdt` (`docPartGallery` "Table of Contents") holding `TOC \o "1-3" \h \z \u` and the entries without page numbers; `w:updateFields` in `settings.xml`, so Word offers to update on open |
| Markdown | `#` levels; numbers written into the heading text when numbered | `[2.3 Results](#2-3-results)` | a nested list of links |
| LaTeX (E9.19) | `\section`, `\subsection` …; unnumbered styles `\section*` | `\label{}` at the target, `\ref{}`, `\nameref{}`, `\pageref{}` | `\tableofcontents` |
| PDF | outline levels as bookmarks (S4) | link annotations | entries as links |

Import is the reverse; a `REF`/`bookmark-ref` whose bookmark does not lie at the start of a paragraph becomes a
reference to that paragraph and reports `reference-position`; one with no bookmark becomes plain text and reports
`reference`. All of it with the `openoffice` / `import-export-wiring` agents, after the model is in.

## 10. Proposed decisions (to be numbered when a block is given)

1. An outline level (1–9) is a property of a paragraph style, inherited along `based_on`; Title has none, Heading 1–6
   have 1–6, and a paragraph is a heading because of it (replaces `HEADING_STYLES` and the layout's `KEEP`).
2. Numbering schemes are document data in a `SchemeBook`, built-ins seeded; a scheme has nine level formats with
   before, after and which levels the label shows; `chapters` is new.
3. A paragraph style may point at a list; its paragraphs are items of that list at their outline level. Number
   Headings points every outline style at the list `outline`.
4. A reference is an inline field at a U+FFFC, holding a thing id and what to show; the shown text is derived in the
   kernel, the page in the layout; a reference to a thing that is gone is shown as broken.
5. Field kinds are a registry in `claudia_core`; citations and page fields will be kinds of it.
6. A table of contents is a generated paragraph holding only its options; its entries are derived and drawn with the
   styles Contents 1–9; flow view shows no page numbers.
7. Page numbers of references and of the table of contents are found by the layout in at most three passes.
8. Exports write the table of contents without page numbers; docx asks Word to update fields on open, ODT reports
   `toc-pages`.
9. The menu entries and keys of section 8.

## 11. Where the code goes

**Replaced on 2026-11-16 by `text-structure-across-apps.md`** (class diagram
`mockups/text-structure-architecture.svg`): what this section put into `claudia-composes` (effective items, the label
cache, `references.py`, `contents.py`, `SetListItem`, the list wire methods) goes into `claudia-core` and a shared
server module, so that creates uses the same code.

## 12. Slices and tests (TDD, tests first)

| Slice | What | Tests first |
|---|---|---|
| **S0** | List markers in the print layout: `TextBlock.label`, the hanging marker (E9.4's gutter rule) | layout: a numbered list and a bulleted list lay out with their markers; display list snapshot |
| **S1** | Outline level, Heading 3–6, `SetStyleOutline`, `block_kind`/layout/editor read it, `aria-level`; ODT/docx outline levels | core: inheritance, inverse, refusal for non-paragraph kinds; composes: a user style with outline 2 is a heading; old states; layout: keep-with-next by outline |
| **S2** | `SchemeBook`, `chapters`, `StyleDef.numbering`, Number Headings, All numbering dialog, `Label.number`; io | the E9.21 counting tests still pass; headings 2, 2.1, 2.2, 3; appendix list; own item wins; one step undoes Number Headings; replay; perf guard with 20 000 paragraphs and numbered headings |
| **S3** | `Toc`, `SetGenerated`, entries, flow view, options, Contents styles; io without pages | entries follow typing, renumbering, outline changes, delete of a heading; refusals (typing into it, joining); two writers (Playwright, Firefox and Chromium) |
| **S4** | Pages: the passes, leader lines, page numbers in page view and print; PDF links and bookmarks | layout: page of a heading, fixed column, a reference that moves a line to the next page settles in three passes; determinism snapshot |
| **S5** | Fields, `RefField`, the picker, the atom, broken state, go to target; io | split/join/delete/undo with fields; U+FFFC stripped from input; redaction keeps fields; resolve per show; reverse index (typing in a heading re-resolves only its references); broken and mended by undo |
| **S6** | Page references ("see page 12") | S4 and S5 together |

S0 to S3 give a usable table of contents before references exist; S5 does not depend on S3 or S4.

## 13. Alternatives considered

| Alternative | Why not |
|---|---|
| A heading is recognised by its style's name (today) | Every user style and every imported style would need to be based on a built-in; the layout and the model already disagree about the list. |
| Number headings with a `ListItem` on each heading paragraph | A numbered heading would be a per-paragraph setting, against D306; turning numbering on would touch every heading; a new heading would have to be made an item by hand. |
| A scheme (not a list) on the style | No start, no continue, no second sequence; docx and ODF link a style to a list. |
| Fields located by offsets in a side table | Every edit would have to move them (as objects' anchors are moved); the U+FFFC tuple needs no following and cannot drift. |
| The table of contents as ordinary paragraphs written on "Update" | The stale-field problem the owner wants gone; hand edits to entries would be lost on the next update. |
| The table of contents as a floating container | Containers float over the text (D563); a table of contents is part of the flow and paginates. |
| Page numbers worked out on the server | Pagination is the client's (D901); a second layout on the server would be the second implementation the layout decision rules out. |

## 14. Open points (each with the default taken here)

1. **Documents from before:** give `heading-1`/`heading-2` outline levels 1/2 on load (default) or not at all.
2. **Own item against style numbering:** a paragraph's own list item wins (default).
3. **Title in the table of contents:** never (default); a document that wants it can give its title style a level.
4. **"Show as number" for a nested item:** the full trail "2.b" (default) or only "b".
5. **Search** looks at the words a reference shows? Default: no (they are derived; searching "2.3" should find the
   heading, not every reference to it).
6. **Cross-Reference… in computes and creates:** shown disabled with a reason (default, as List); or composes only.
7. **The AI** reads shown references and labels but does not insert references or tables of contents in this round
   (structure, as with lists, D63); act mode may later.
8. **Number Headings on a document with no headings:** the entry is still enabled and says nothing happened? Default:
   it turns numbering on for the heading styles, which then number the first heading typed.

## 15. Risks

- **The shared `Paragraph` grows two fields** (`fields`, `generated`) that creates text boxes do not use yet; both are
  written only when set, so creates' snapshots and tests stay unchanged (as with `item`).
- **U+FFFC in the wild:** imported text and pasted HTML may contain U+FFFC; it is stripped at every entry point, and a
  test guards each (paste, import, `replace_text`, suggestions).
- **contenteditable and atoms:** caret mapping (`textBefore`, `data-skip`) must count the atom as one character; Firefox
  and Chromium differ around `contenteditable="false"` at a line's end. A short spike first in S5.
- **Three-pass layout and performance:** a long document laid out three times. The first pass is cached; only
  paragraphs with page references are laid out again, and the table of contents never.
- **Screen readers** with numbered headings: the number is drawn by CSS; `aria-label` on the heading must include it
  so "2.3 Results" is read, not "Results".
