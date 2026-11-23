# Layouts and templates in the creates model and the server (E10.4, E10.22, D1530–D1539)

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
  `update_layout`, `delete_layout`, `remove_slide_command`. D1536: the plans that leave a provisional, unnamed layout
  without a follower end with its removal, in the same batch (undo brings it back).
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
6. D1536 (decided by the owner): an unnamed provisional layout nobody follows is removed by the step that made it
   unused. A client that sends the plain `SetSlideLayout` or `RemoveSlide` can still leave one behind.

## Measured

`settle` scanned all bound objects after every command: 1.7 ms of 4.7 ms per command on 6,000 objects (D1531), and
62.7 ms when all 6,000 are bound (PERF-12). It now looks at what the command touched (an `_ObjectTable` that records
writes and followers): 4.3 ms in the second case.

## Fixed after the review (owner's wish, 2026-11-23)

* PERF-12 as above.
* CODE-83: `SetSlideLayout` carries `frames` in its inverse, so that undoing the binding of a free object gives its
  place back; undoing a change from an inert binding is no longer refused.
* CODE-84: a layout's id is a part for redaction.

## Known gaps

* Layout `purpose` and the origin `"template"` are unused until patch 2 and E10.24.
* The web does not draw layout objects yet; no menus (Format ▸ Layout / Template with keys in `claudia-menus.xlsx`) —
  patch 3.

## What could not be run

* Web lint, tests and types, layout tests and E2E (`@core`, "use it before delivery"): no `npm install` in this
  workspace, and there is no UI for layouts yet — nothing a user could do.
* `check_debt` without `--fast` (docs build, perf guards).
* Desktop clients: no UI change; the Linux client tests pass.

## BITV

No UI in this patch, nothing diverges. The mocks (A10) keep to the grid and give every control a text label.


# Patch 2 — templates: the model, the file and the server API (D1537–D1539)

Patch 1 and 1b are assumed applied. Test seams, confirmed by the owner: (1) the creates model, (2) the file, (3) the
server API, plus core's `Theme`.

## What was built

* **Core** — `Theme(name, styles, palette)` and `theme_commands`: the commands that give a document the styles and
  colours of a theme (D1539). `ReplacePalette` refuses a palette that lacks a role a style uses, so the new palette is the
  document's roles with the theme's on top, plus theme-only roles; colours are normalised to upper-case hex.
* **Creates model** — `TemplateInfo` (name ≤ 80, purpose ≤ 400, language a tag; refusals are translated), kept in the
  state under `template` (state schema **20**), `SetTemplate` / `TemplateChanged`; `template.py`: `template_state`,
  `check_template`, `basic_template`, `start_from_template`, `plan_change_theme`, `plan_change_template`.
  `layout_plans.free_id` is public.
* **The file** (D1537) — `claudia_server.template_library.template_file` / `read_template_file`: a Claudia export with
  the parts `format`, `export.json`, `content.json` only.
* **The library** (D1537) — `TemplateLibrary(folder)` (`check` is what the admin's check and `add` share): built-in Basic (name and purpose said in the language asked) and
  the files under `STATE_DIR/templates/<id>.claudia-export.zip`, rebuilt from what was checked (no history, no chat);
  names unique ignoring case; the id is a slug of the name, made unique with `-2`, `-3`…; files are written whole
  (temporary file, then replace).
* **HTTP** — `GET /api/templates?locale=`, `POST /api/templates/{id}/upload?locale=` (D1538: the new presentation as a
  held upload for `hello` + `create` + `upload`; things named in the locale; same gate as `POST /api/uploads`);
  `GET`, `POST /check`, `POST`, `DELETE /api/admin/templates…` (administrators only, whole page as answer, 400 with a
  sentence, 409 for a taken name or for Basic, 404 for an unknown id).
* **Methods of a presentation** — `template`, `save_as_template` (`leaves="export"`, assistant refused),
  `change_theme`, `change_template` (`write`, `base`), via `Context.template_library`. The `template` event is content in
  the audience table; the four methods read `content` in `tests/method_reads.json`.
* **i18n** — 16 new strings in German (the sentences of the refusals, the name and purpose of Basic); pot, po,
  pseudo-locale, both `.mo`, web catalog and API snapshots regenerated. Refusals of `TemplateRefused` are written
  `TemplateRefused(N_("…"))` so the extractor finds them.

## Assumptions

1. Styles keep their origin when a deck starts from a template.
2. A colour role only the deck has, whose *name* is the name of a role of the theme under another id, makes the step
   refuse with "There is already a colour role named …" (names are unique in a palette). Nothing is changed; the person
   renames the role and tries again. A role only the deck has is never dropped.
3. A matched style takes only the CSS of the theme; its parent, headings, numbering and name stay.
4. An asset id that already exists in the deck is not redefined by Change template, even if its content differs.
5. A template must carry its note: a plain slide-less export is refused with "choose Save as template… in it first".
6. The admin routes send the file again for the add instead of holding it between check and add (a template is a few
   hundred kilobytes; at most 16 MB). The list of the admin page says the built-in name in English with `builtin: true`;
   the page translates it.
7. A template file is stored under the slug of its name, so renaming is "remove and add again".
8. Change template replaces the objects of a matched layout with the template's (D1539, **to confirm**), and a matched
   layout keeps its own `hidden` flag and `purpose`.
9. The name and the purpose of a template are plain text in one line: no control characters, no bidirectional controls
   (they end up in the upload name, the history and the lists). A file in the templates folder that is no template, has
   a name or an id another template has, is left out and logged, never fatal. A state nothing can restore is "not a
   presentation", whatever the restoring raised.
10. The library reads its folder once at start and after each change by this server; a file put there by hand needs a
   restart.

## What could not be run

* Web lint/tests/types, layout tests and E2E (`@core`, "use it before delivery"): no `npm install` in this workspace,
  and patch 2 has no UI. The scenarios of `templates.feature` stay `@draft` until patch 3 binds their steps.
* `check_debt` without `--fast` (docs build, perf guards).
* Desktop clients: no UI change; the Linux client tests pass.

## BITV

No UI in this patch, nothing diverges. The admin page and the cards of File ▸ New (patch 3) will need text labels,
focus order and a keyboard path for Add template…, Remove and the card choice.
