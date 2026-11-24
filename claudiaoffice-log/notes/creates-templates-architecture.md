# Templates and layouts in creates: architecture proposal

Status: proposal, step 4 of the work process. Nothing is decided until the owner agrees. Diagrams:
`mockups/creates-architecture-1-packages.svg` (where things go), `-2-classes.svg` (the model), `-3-flows.svg` (the flows).

## The shape in one paragraph

A **layout** is a slide-shaped holder of objects that lives in its own list next to the slides. A **placeholder** is an
ordinary object on a layout whose anchor carries a purpose label. A slide object that copies a placeholder is marked
`bound_to_placeholder` (a technical field, separate from the purpose). A **template** is not a new thing in the code: it is a creates presentation without slides. A
**theme** is a named styles-plus-palette pair that has to exist outside a document, so it is the one new class in core
besides `Layout`.

## Q2: layouts as holders (answer: yes, in a second list)

What the code showed:

* `ObjectModel.holders()` is called in exactly one place in core, `objects_to_data` (saving). Everything that walks
  slides (show, print, export, outline, search, reading order) uses `SlideModel.slides` directly.
* So `holders()` stays "the slides". New: `layout_holders()` (default `()`) and `all_holders()` (both; used only by
  `objects_to_data`). Show, print, export and outline therefore never see a layout without any change to them.
* Layout objects live in the same `objects` dict and `_stack` as slide objects, so every existing object command
  (add, move, resize, rotate, retext, remove, undo, locks, events) works on layouts unchanged.
* Layout ids have their own prefix (`l1`, `l2`…); slide ids stay `s1`…
* A layout's own name is not in the Thing namespace (it is not a Thing); it is unique inside `Layouts`, like a style's
  name inside the `StyleBook`. The *objects* on a layout get server-given names as every object does (D550).

Cost left: `check_anchor` must accept a layout id as a holder (same bounds as a slide), and E6.31's `slides.py` is
unmerged. Layouts would be a sibling of `Slides` in a new `layouts.py`, so we should build on E6.31's branch or after it
merges (decision A1).

## Placeholders and bound objects (no new object kind)

Two fields with two different jobs (diagram `mockups/creates-architecture-5-bound-copy.svg`):

* `SlideAnchor.purpose` (on a layout object): the placeholder's label. User-facing and semantic: shown in the UI, unique
  within its layout, and matched by name when a slide changes layout.
* `SlideAnchor.bound_to_placeholder` (on a slide object): technical. The id of the placeholder object this object copies
  its frame from. A slide object never stores a purpose; it is looked up through the placeholder, so renaming a purpose in
  the layout renames it everywhere.
* Why the anchor and not the body or a side table: the anchor travels with `AddObject`, `RemoveObject` and undo, so no
  creates command keeps a side table in step, and the body (`_BODY_FIELDS`, shared by three apps) stays untouched.
* A placeholder's style is a normal object style plus the text paragraph's style. It does not restyle text already in a
  bound object; changing a style stays Edit style, which is deck-wide already.
* Empty placeholder: hint text while editing, nothing in show, print and export.

## Decision A2: a bound copy, refreshed after every command

A bound object keeps real coordinates (x, y, w, h) and its object style, marked read-only by `bound_to_placeholder`. The layout is the truth;
the copies are a cache. Every consumer keeps reading ordinary objects, and a slide stands on its own without the layout.

* After every command `settle` repairs the copies (frame and object style) from the layouts. It repairs; it never refuses a command. So a layout
  update is one step ("move the placeholder") and carries no list of followers; a follower added meanwhile by a colleague
  is repaired too; undo passes through no state anything checks.
* Commands may not change the frame or the object style of a bound object. Setting or clearing `bound_to_placeholder` is a normal change
  (`SetSlideLayout`, delete placeholder).
* Repair rules: placeholder moved or resized, copy its frame into every object bound to it; placeholder gone or the slide's
  layout changed without a new binding, clear `bound_to_placeholder` (a free box where it stands).
* Free box from a bound object: drop `bound_to_placeholder`; the copy already is its frame.
* Inside a command, between steps, a copy may lag; code there calls `model.frame_of(obj)`, which reads the layout.
* To confirm in the first TDD step: that `settle` may change objects and emit `ObjectsChanged` for them (its docstring says
  "recalculate here"); that the copies are deterministic on replay; how the web client learns of the changes; that the
  repair only visits layouts and slides the command touched.
* Rejected alternatives: no stored frame at all (every reader resolves, dead fields, events for followers); stored copies
  with an invariant that refuses commands (a compound command's intermediate states, undo, and a concurrent follower break it).

## New and changed classes

Core (`claudia_core`): `Layout`, `Layouts` (`layouts.py`); `Theme` (`theme.py`); `SlideAnchor.purpose` and `SlideAnchor.bound_to_placeholder`;
`ObjectModel.layout_holders/all_holders`; `SlideNumberField` registered in `FIELD_KINDS` (a slide number needs it;
`generated.py` already knows slide numbers; ties to E10.21). Unchanged: `StyleBook` (origin builtin/template/document,
D780), `Palette` (`replace_all`), `Batch`.

Creates (`claudia_creates`): `SlideModel` gains `layouts`, `slide_layouts` (slide id → layout id) and `template_origin`
(a note, never followed); state schema 18; restore of schema 17 gives one built-in basic layout and every slide on it.
`template.py` holds `Template` (read view), `check_template`, `start_from_template`, `plan_change_theme` and
`plan_change_template`. `layout_commands.py` holds the commands.

Commands (each carries final values and returns its inverse, as the rest do):

| Command | What it does |
| --- | --- |
| `DefineLayout`, `RemoveLayout` | inverse pair; `RemoveLayout` names the layout its slides move to (default basic); built-ins are only hidden |
| `RenameLayout`, `HideLayout` | as for styles |
| `SetSlideLayout(slide, layout, rebind)` | picker, delete layout, change template; `rebind` is worked out by the model and carried: an object whose placeholder's purpose exists in the new layout is bound to that placeholder (Q22), otherwise its binding is cleared (a free box at its current frame) |
| `DeviateLayout(slide, object, change)` | the offer flow's first step: provisional layout named after its parent, copy of the parent's objects with the change applied, slide put on it; one undo step. The object is a placeholder-bound object of the slide or an object of the layout itself |
| `Batch` of existing commands | "Update layout · n slides instead" (move the placeholder, put the slides back on the parent with their bindings, remove the provisional layout; `settle` copies the frames); delete placeholder; change theme; change template |

Unnamed, unused layouts are removed when the last slide leaves them (the rule from the offer flow); that is a rule in
`SetSlideLayout`, not a timer.

## Template as an export (Q24)

* **Save as template…** (anyone): server-side `Template.of(model)` copies the presentation without slides, keeps the assets
  layout objects use and drops slide-only assets, then the existing `write_export` writes it. It is a logged unencrypted
  export (D108/D145): content only, no history, no chat.
* **Add to server** (admin): Server settings ▸ Templates, same shape as Fonts (D1041): held upload, `check_template`
  (reads as an export, creates, no slides, at least one layout, unique name), then add; every answer is the whole page.
  Stored as files under the state directory. The basic template is built in and cannot be removed.
* **New from a template**: `start_from_template` copies styles, palette, layouts, layout objects and assets, adds `s1` on
  `layouts.first()`, and the existing import path creates a new sealed document with the importer as owner (D108), not
  logged as an exit.
* **Change theme / template**: the client gets the template (or its theme) from the server, the model plans a `Batch` of
  final values, the client shows the preview, then sends it. The server applies a command like any other and never
  consults the template again.
* No change in `claudia-document-file`: no new file type.

## Clients

The web page is the same inside the GTK and Neutralino shells; shells only draw menus and send actions
(`clients/contract`). So new code is web-side (`layout-host.ts` modelled on `style-host.ts`, the strip, the preview dialog,
All layouts…, the purpose cards in File ▸ New, the admin page) plus new action ids in the contract, with the menu entries
and key shortcuts added to `claudia-menus.xlsx`. No divergence between web and desktop is introduced.

## Glossary impact (Q12) — drafts, nothing written

New: **Theme**, **Template**, **Layout**, **Placeholder**. Changed: Holder ("The slide, **layout**, sheet or paragraph an
object is at"), Object layer ("… of a page, a slide, **a layout** or a sheet"), Style and Palette lose "theme" from their
avoid lists and Palette is reworded ("…shared by all its styles; with the styles it makes a theme"). Not added: "Definition"
(dropped earlier); "purpose label" is part of Placeholder's entry, not an entry.

* **Theme**: A named set of styles together with the palette they refer to, which can exist without a document.
  _avoid_: skin, look
* **Template**: A named combination of layouts and a theme with a purpose; a new presentation starts as a copy of it and
  keeps no link to it.
  _avoid_: master, POTX, design
* **Layout**: A named arrangement of placeholders and other objects that a slide follows.
  _avoid_: slide master, slide type
* **Placeholder**: An object on a layout, labelled by its purpose, that an object on a slide can take.
  _avoid_: slot, frame

## Decisions to take

| | Decision | Recommendation |
| --- | --- | --- |
| A1 | Build on E6.31's `slides.py` (merge first) or add `layouts.py` on top of it later | wait for E6.31 to merge; layouts are a sibling of `Slides` |
| A2 | How a slide object gets the frame of its placeholder | bound copy, read-only, refreshed by `settle` after every command |
| A3 | Purpose and `bound_to_placeholder` in the anchor, or in a side table | anchor, two separate fields |
| A4 | `Theme`, `Layout`, `Layouts` in core, not creates | core (composes page styles E9.14 may reuse them) |
| A5 | `Template` as a read view, not a class that is stored | view |
| A6 | Second holder list (`layout_holders`) | yes |
| A7 | Server keeps template files only; the model reads them through `check_template` | yes |
| A8 | Slide number as a new field kind in this work or in E10.21 | E10.21, templates do not wait for it |
| A9 | Split into patches: (1) core + creates model and commands, (2) template read/write + server, (3) web UI | yes, each with its own scenarios |
| A10 | Menu placement and shortcuts as in the mock of Format ▸ Layout / Template; Save as template… under Format ▸ Template | as mocked, still to confirm |

## Settled in the grill after the proposal (Q25–Q35)

* Glossary entries written (Q25). Backlog E10.4, E10.5 reworked and E10.22–E10.25 added (Q31, Q32).
* Placeholders are made only by editing a layout (Q26); a free object can be pasted into the layout editor and marked there.
* **What triggers the offer (Q27, Q34).** Any change on a slide to something connected to its layout: for an object that
  takes a placeholder its frame, rotation, deletion and its own look (object style, fill, border); typing and text
  formatting never (text styles keep the E9.7 offer). For other layout objects (a logo, a footer, a slide number) any
  change, their text and picture included. Free objects never trigger it.
* **Layout objects (Q33).** Not copied onto slides. They are drawn from the layout beneath the slide's own objects and can
  be selected on a slide; a change goes through `DeviateLayout` on the layout's own object. Only placeholders have bound
  copies. This keeps a 200-slide deck free of hundreds of extra objects, names, search hits and reading-order entries; the
  slide number field is evaluated per slide when drawing.
* **When the strip appears (Q35).** The first change starts the provisional layout and later edits go into it; the strip
  appears when the user leaves the box or deselects the object, not after each keystroke.
* A deck has no purpose of its own beyond the note of its template (Q28); deleting the last slide is allowed and a deck
  without slides is a template, entered through Format ▸ Layout ▸ All layouts… (Q29); the first layout is the first visible
  one in list order, movable with Move up and Move down (Q30); pptx/odp masters are E10.24 (Q31).

## Still open

Nothing from the grill. To settle in the build: that `settle` may change objects and emit events (A2); BITV: the dialogs
need a list alternative to the thumbnails ("Show as list"), keyboard operation of the strip, and a text for each
thumbnail; I18N: built-in layout and theme names go through gettext, server template texts stay in the administrator's
language with a stated language.
