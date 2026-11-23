# Layouts in the creates model (E10.4, D1530–D1536)

Branch `e10-4-templates-and-layouts`, first of three patches. Design: `notes/creates-templates-architecture.md`;
decisions D1530–D1536; words: glossary (Layout, Placeholder, Provisional layout, Bound copy).

## Split

1. **This patch** — core and creates model: layouts, placeholders, bound copies, the commands and plans, export
   flattening, state schema 19.
2. Template read/write, `Theme`, server library and admin page, new-from-template, save-as-template, change
   theme/template, menu workbook keys.
3. Web UI and E2E binding of `specs/creates/layouts.feature` and `templates.feature`.

## What was built

* `claudia_core.layouts` — `Layout`, `Layouts` (`require`, `check_name`, `first_visible`, `add` with bounds check,
  `change`, `move`, `remove`). A layout name is non-empty and unique ignoring case; both are `Refusal`s (translated).
* `ObjectModel.layout_holders()` / `all_holders()`: layouts hold ordinary objects through holders and share one id
  namespace with slides. `placed_at(old, new)` lets Move, Resize and Rotate keep `purpose` and `bound_to_placeholder`.
* `SlideAnchor` gained `purpose` (people) and `bound_to_placeholder` (code), written only when set (D1532).
* `claudia_creates.model` — `layouts`, `slide_layouts` (state schema **19**; absent means every slide on "basic"),
  `define_layout`, `change_layout`, `move_layout`, `remove_layout`, `put_slide_on_layout`, readers
  (`layouts_to_choose`, `layout_of`, `layout_objects_of`, `objects_drawn_on`, `placeholder_of`, `slides_following`).
* `layout_commands.py` — `DefineLayout`, `RemoveLayout`, `RenameLayout`, `HideLayout`, `MoveLayout`,
  `SetSlideLayout`; all with exact inverses. `AddSlide.layout` lets undoing `RemoveSlide` restore the layout.
* `layout_plans.py` — plans that return commands with final values: `set_layout_command`, `deviate_layout` (D1533: a
  provisional layout "Parent 2" holding copies of the parent's objects, the slide moved onto it, the change retargeted),
  `update_layout`, `delete_layout`.
* Bound copy (D1531): `SlideModel.settle` repairs bound objects from their placeholder and emits `ObjectsChanged`; it
  never refuses and never clears a binding, so undo restores it. A binding to a placeholder of a layout the slide does
  not follow is inert. `replace_object` refuses to move, resize, rotate or restyle a bound object ("change the layout
  instead").
* Export: pptx and odp write `objects_drawn_on(slide)` — layout objects flattened under the slide's own, empty bound
  boxes left out. `layout_losses` reports `Loss("not-written", "layouts", n)` for slides whose layout differs from the
  baseline (masters and placeholders are E10.24).
* Server: "layouts" and "slide_layout" are classified as content in `audience.py`.
* i18n: three refusals in German; pot, po, pseudo-locale, both `.mo`, web catalog and API snapshots regenerated.

## Assumptions

1. A new slide follows the layout of the slide before it, the first slide the first visible layout.
2. Deleting a layout moves its slides to the next visible layout (or the previous one), and deleting a placeholder also
   removes the empty bound boxes on the slides.
3. A provisional layout's number is the first free one starting at 2.
4. `purpose` is unique per layout and only allowed on a layout's object.
5. Layout object text is not covered by redaction (layouts hold no user content until E10.24 imports some).
6. D1536 is **undecided**: unnamed layouts nobody follows are hidden from `layouts_to_choose`, not deleted. Owner to
   decide whether they should be removed automatically.

## Measured

`settle` scans all objects after every command: 1.7 ms of 4.7 ms per command on a deck of 6,000 objects (D1531). Fine
for decks of normal size; an index of bound objects per placeholder would remove it (tech debt, PERF below).

## Known gaps

* `SetSlideLayout.rebind` that binds a previously free object cannot restore its frame on undo. No plan does this yet.
* Layout `purpose` and layout origin `"template"` are unused until patch 2 and E10.24.
* The web does not draw layout objects yet; no menus (Format ▸ Layout / Template with keys in `claudia-menus.xlsx`) —
  patch 3.

## What could not be run

* Web lint, tests and types, layout tests and E2E (`@core`, "use it before delivery"): no `npm install` in this
  workspace, and there is no UI for layouts yet — nothing a user could do.
* `check_debt` without `--fast` (docs build, perf guards).
* Desktop clients: no UI change; the Linux client tests pass.

## BITV

No UI in this patch, nothing diverges. The mocks (A10) keep to the grid and give every control a text label.
