# claudia composes — ordered and unordered lists (design proposal)

**Status: agreed 2026-11-13; kernel, server and web are built (branch `lists-and-anchors-in-compose`); creates bullets and the native menus are open (section 0).** Asked for by the owner on 2026-11-12. The screens are in
`mockups/composes-lists.svg` (PNG beside it) and are to be agreed before any UI code (project rule). No decision
numbers are taken yet: when this is agreed, ask for a block in `decision-log/ranges.md` (D271–D280 are free) and turn
section 3 into decisions. Stories: E9.21 (lists, this note) and E9.22 (anchors and numbered headings, section 4).

## 0. What was decided and built (2026-11-13)

The owner agreed the screens and the menu place and decided: the branch is `lists-and-anchors-in-compose`; **Format ▸ List
goes into all three apps at once**, for consistency, even where it does nothing yet; **a list has an explicit identity
and an optional `name`** (kept in the background for now, meant for later user-given names that references can point
to); creates text boxes are to show bullets too.

Differences between the proposal below and what was built:

- **The scheme registry lives in `claudia-core`** (`claudia_core.lists`: `SCHEMES`, `ListDef(id, scheme, start, name)`,
  `ListBook` with a change counter, `numbering_labels`, the commands `CreateList`/`ChangeList`/`RemoveList` and the
  event `ListsChanged`), not in composes, so that creates and computes can use it without a second model. `ListItem`
  and `Paragraph.item` are in `claudia_core.paragraphs`. Composes holds the book (`TextModel.lists`), state schema 6.
- **Labels are cached** on (structure counter, book version); typing never works them out again, and a command sends
  `LabelsChanged` only for the labels that differ (a perf test guards both).
- **Markdown** writes nested items with 4 spaces per level, not the 2 of the design: CommonMark needs the width of the
  marker (`1. `) to nest, and 2 spaces would flatten numbered lists in other readers.
- **Format ▸ List in the web menu has no action id** (it is not in the native shells' manifests yet), so GTK, Windows
  and macOS menus do not show it; their manifests and the shell contract need `format.list.*` actions (open, see 6).
- **Shortcuts** Ctrl+Shift+8 / Ctrl+Shift+7 are matched by the physical key (`code`), because the shifted character
  depends on the keyboard layout.
- **Not built:** bullets in creates text boxes (`ObjectBody` holds one `Paragraph`, a list needs several: its own
  slice); the assistant may not make lists (D63, refused like other structure edits); import/export; anchors (E9.22).
- Checked in a real browser with two writers (`web/e2e/lists.cjs`, Chromium); Firefox is for the owner to run
  (`BROWSER=firefox node e2e/lists.cjs`).

## 1. What was asked

Ordered and unordered lists first. Behind it a bigger wish: numbered headings that can appear in a table of contents,
and **referencable anchors** for in-document references (to a heading, a paragraph or another anchor), with a good UI
for managing enumerations. This is the part of MS Office that confuses people again and again, especially together
with cross-references. So lists are built so that the bigger wish does not need a second model (section 4).

## 2. What the code has today

- A text is a flat list of paragraphs (`TextModel.blocks`). A paragraph is the shared `claudia_core.Paragraph`
  (D181): `id` (never reused), `style`, `text`, `runs` (authorship). It is immutable; commands return their exact
  inverse.
- Structure commands: `SplitBlock`, `JoinBlocks`, `SetStyle`. `next_style` decides what Enter starts. Spans, cursors,
  zones, suggestions and floating objects all follow edits through `TextCommand.follow`.
- D306: no direct formatting; the text of a container has one style. D62/D73: styles first, named by purpose.
- The web editor never edits the page itself: every input becomes a request and the page changes when the server's
  events arrive (`TextEditor.vue`, `blocks.ts` mirrors the commands' `follow`).
- There are **no lists**. The ODT importer flattens list items into plain paragraphs and reports a `list` loss (D402,
  D405); the docx importer treats "List Bullet" as an unknown style.

## 3. The proposal

### 3.1 Structure is not look

A list item is *structure*, like a heading level. Its look stays with styles (D306): an item keeps its paragraph style
(Body text, Quote, …). What a list adds is a **mark** on the paragraph and a **scheme** that says how markers are drawn
and how far each level is indented. Bullets and numbers are never characters of the text.

### 3.2 The model

```
Paragraph.item   : ListItem | None          ListItem(list: str, level: int)      level 0..8
TextModel.lists  : dict[str, ListDef]       ListDef(id: str, scheme: str, start: int = 1)
SCHEMES          : code, like BUILTIN_STYLES  "bullets": • ◦ ▪ (then again)
                                              "numbers": 1. a. i. (then again)
```

- **A list is explicit.** Items that share a `list` id are one list, in document order, even if a note sits between
  them. Items of two different lists never count together, even when they are neighbours. This is what ODF
  (`text:list`, `text:continue-list`) and docx (`numId`/`ilvl`) have too, so import/export can keep it.
- **The scheme is named** and lives in a registry, like styles: one definition for every list that uses it, and the
  place where the later enumeration manager edits formats, indents and gaps. Only the two built-in schemes exist in
  this round (defined in code, re-seeded on replay, like the built-in styles).
- `item` is an optional last field of the shared `Paragraph` (serialised only when set), so a creates text box can show
  bullets later without a model change. Only composes gets the registry, the commands and the UI now.
- State schema 5 → 6. Old states load (no `item`, no `lists`); the app is pre-release, so nothing else is kept.

### 3.3 Labels are derived, in the kernel, never stored

`numbering.labels(blocks, lists) -> dict[block_id, Label]` is one pure function:
`Label(marker: str, path: tuple[int, ...] | None)`. `marker` is what is drawn ("•", "3.", "b."); `path` is the number
trail of a numbered item (`(2, 1)`), `None` for bullets.

Counting rules (also in panel C of the mock-up):

1. Counters are per list and per level. An item of level *n* adds one at level *n* and resets every deeper level.
2. A level with no item above it in its list starts at the list's `start` (level 0) or 1 (deeper). A missing parent
   counts as none, so the function is total: a deleted parent never makes numbering fail.
3. Alpha counts a…z, aa…, roman counts up to 3999 and falls back to decimal after that.

**Why in the kernel and not in the browser.** The layout algorithm is written once, in TypeScript (the owner's stance
of 2026-11-12, not yet in the decision log); numbering is not layout but document semantics, and the Python exporters
(ODT, docx, later LaTeX), the AI and later references all need the same answer. The editor is already server-driven, so it only *displays* labels
the server sends. There is no second implementation to disagree. The layout module takes the label as an input (its
width matters for the hanging gutter, E9.4).

`TextModel` counts structural changes (split, join, set item, list changes). `settle` runs `labels` only when that
count moved, diffs against the last result and emits `LabelsChanged`. Typing does not recompute. A perf guard
(20 000 paragraphs, many structural commands) goes in the existing `test_performance.py` style.

### 3.4 Commands, events, server methods

Commands (each returns its exact inverse; `regions` is the paragraph's text range, like `SetStyle`, so a colleague's
± n words zone refuses the change with `locked`; `shifted_by` returns `None` when the paragraph was joined away):

| Command | Inverse |
|---|---|
| `SetListItem(block, item \| None)` | `SetListItem(block, old)` |
| `CreateList(id, scheme, start)` | `RemoveList(id)` — only as the undo of a create, refused while an item uses it (as `RemoveStyle`) |
| `ChangeList(list, scheme?, start?)` | `ChangeList` with the old values |

- `model.split` copies `item` to the new paragraph (Enter in an item gives an item; pasted lines become items);
  `model.join` keeps the first paragraph's item, and the inverse of a join puts the removed paragraph's item back
  (`SetListItem` in the same batch). `next_style` is unchanged.
- Events (new, small, like `StyleChanged`): `item {block, item}`, `lists {lists}`, `labels {labels}`. The `split`
  event needs no field: the client copies `item` as the model does, and `blocks.ts` mirrors that rule.
- Server methods, each one request = one history step (a `Batch` with a sentence for the history):
  `make_list(blocks, scheme|null)` (null takes the list away), `indent_item(blocks, by)`, `continue_list(block)`
  (the block's list takes over the nearest earlier list of the same scheme), `list_start(list, start)`. `blocks` answers
  each paragraph with `item` and `label` and adds `lists` and the schemes' geometry. All additive: a minor bump of
  `claudia-server`, API snapshot and changelog updated.

### 3.5 Editing rules (panel C)

| Key | Rule |
|---|---|
| Enter | In an item: new item, same list and level. On an empty item: outdent; at level 0 leave the list. This is the *session's* rule, as in every editor; `replace_text("\n")` stays plain text so the API is not context-sensitive. |
| Tab / Shift+Tab | Indent if the paragraph above is an item at the same or a deeper level; outdent if level > 0. |
| Backspace at the start | Outdent, then leave the list; only then join with the paragraph above. |
| Ctrl+Shift+8 / 7 | Bullets / numbers for the selected paragraphs (or the one with the caret): a **new** list at the paragraphs' current levels. If every selected paragraph is already such an item, the list membership is removed; if the selection is exactly one whole list of the other kind, that list changes scheme instead. |

A list started later begins at 1; **Continue previous list** joins it to the nearest earlier list of the same scheme,
and **Start at…** sets the first number. Both are visible, undoable commands, so "why did my numbering restart?" has
a visible answer and a one-click fix.

### 3.6 Web

- The marker is drawn by CSS `::before` from a `data-marker` attribute on the paragraph element, hanging in the left
  gutter, in the paragraph's own font and colour. It is not DOM text, so selection, copy, find and the caret mapping
  (`textBefore`, `data-skip`) are untouched. Check in **Firefox** (the owner's main browser) and Chromium.
- Indent is `(level + 1) × scheme indent`. Between two neighbouring items of one list the gap is the **scheme's
  gap**, not the style's `margin-bottom`, so the last item keeps the full margin and no "List item" style is needed.
- Format ▸ **List ▸** (Bulleted, Numbered, Continue previous list, Start at…, Indent, Outdent) between "All styles…"
  and "Colours…", and four buttons in the style bar (`StyleBar.vue`). D300 gave the Format menu four entries in all
  three apps; this is a composes-only addition (open point 1).
- `markdown.ts` writes `- ` / `1. ` with two spaces per level, a tight list without blank lines, and the **derived**
  number (so a continued list prints `3.`).

### 3.7 Import and export (follow-up, with the `openoffice` agent)

`text:list` + list style ↔ list + scheme + level (`text:start-value`, `text:continue-list` ↔ `start` and list identity);
docx `numPr` ↔ the same; LaTeX `itemize`/`enumerate` with `\item`; Markdown as above. Schemes with custom formats stay
losses (`list`, D405). Until then the importers keep flattening and reporting `list`.

## 4. The seam: anchors, numbered headings, references (E9.22, not built)

What lists add is a *label derived from structure*. The three things the owner named need the same mechanism:

- **Anchor.** Anything with a stable id that a reference can point at. Every paragraph already is one (`b17`, never
  reused; a paragraph joined away hands its objects to the survivor, and a reference can follow the same way). Later
  bookmarks, figures, tables, equations.
- **Label.** What `labels()` gives: nothing (plain paragraph), a marker (•), or a number path (2.3.b). A *numbered
  anchor* is one whose label has a `path`.
- **Reference.** An inline item that stores an anchor id and *which part of the label* to show (number, number and
  text, text, later page). It never holds a typed number. Move the step and the reference follows; delete the target
  and it is shown as **broken**, not silently stale.
- **Numbered headings.** A *style* names a scheme and a level ("Heading 1 → Chapters, level 0"), not each paragraph, so
  D306 holds and "Heading 1 is numbered" is one switch in the style editor. `labels()` then also takes the style
  book: the signature is the only thing that changes.
- **Enumeration manager.** An "All numbering…" dialog beside "All styles…": the schemes with a preview, per-level
  format, indent and gap, which styles and which lists use each. It edits the registry of 3.2.

Why this avoids the MS Office confusion: (a) numbering is a named, visible scheme that styles *refer to*, not a hidden
layer beside the styles; (b) labels are derived after every structural command, so no field needs a manual refresh;
(c) restart and continue are explicit commands on an explicit list, not a guess.

## 5. Alternatives considered

| Alternative | Why not |
|---|---|
| A tree (list → items → paragraphs) | Breaks the flat `blocks`, `follow`, ids, objects' `BlockAnchor` and the shared `Paragraph`. |
| Styles only ("Bullet 1…", "Number 2…") | One style per kind and level; continue/restart has no home; the look of structure is mixed with the structure. |
| A list is a run of neighbouring items (no ids) | Simplest, but a note between two items splits the list, and ODF/docx have ids, so round trips lose information. |
| Numbers computed in the browser | A second implementation next to the exporters' and the AI's; the layout rule of "written once" would be bent. |
| Markers as typed characters | The thing this design exists to avoid. |

## 6. Open points for the owner (each with the default taken here)

1. **Format menu.** A composes-only "List ▸" between "All styles…" and "Colours…" (D300 says four entries in all apps).
   Default: yes, and the four toolbar buttons.
2. **Where `item` lives.** Optional field on the shared `Paragraph` (default) or a composes-only subclass.
3. **Explicit list identity** with Continue / Start at (default) rather than "a list is a run of neighbours".
4. **Tab rule** of 3.5: the first item of a list cannot be indented. Default yes.
5. **Partial selection** makes a new list rather than converting the whole list (3.5). Default yes.
6. **Shortcuts.** Ctrl+Shift+8 / 7 (Google Docs) by default; LibreOffice uses Shift+F12 / F12.
7. **Autoformat** ("- " or "1. " at the start of a line): not in this slice; wanted later?
8. **Item gap from the scheme** and no separate "List item" style (3.6). Default yes.
9. **The AI and structure.** Text suggestions replace characters; "turn these lines into a list" is a structure change
   and needs its own proposal (E9.9, E7.x). Not covered here.
10. **Layout (E9.4).** A label wider than the gutter ("xviii.") pushes the text right like a tab stop; to be fixed by
    the layout module, which gets the label as input.

## 7. Slices and tests (TDD, tests first)

1. **Kernel** (`claudia-composes`, `claudia-server`): `ListItem`, `ListDef`, schemes, `numbering.labels` — tests for
   the counting rules (interrupted list, nested restart, start-at, missing parent, alpha beyond z, roman fallback,
   two neighbouring lists); the three commands with undo and `UndoConflict`; split/join inheritance and their
   inverses; locks; replay of a log (documents are forever: a v5 state and an old log still open); the events; the
   server methods and the API snapshot; the perf guard.
2. **Web**: `blocks.ts` replica and its mirror of split/join, `data-marker` drawing, Enter/Tab/Backspace rules in the
   session, buttons, Format ▸ List, shortcuts, `markdown.ts`; a Playwright scenario with two writers (indent while a
   colleague types elsewhere) run in Firefox and Chromium.
3. **Interchange**: ODT and docx import/export, LaTeX, losses; with the `openoffice` agent.

## 8. Risks

- Touching the shared `Paragraph` reaches creates and its text boxes: `to_data` writes `item` only when set, and the
  creates tests must stay unchanged.
- **Screen readers.** The editor is a flat contenteditable, so list semantics (`role`, `aria-level`) need a short
  spike with Orca and NVDA before the web slice is called done.
- Labels arrive one round trip after the change, like typed text: consistent with the rest of the editor, but visible
  on a slow connection.
