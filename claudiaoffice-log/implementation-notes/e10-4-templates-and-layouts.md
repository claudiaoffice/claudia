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
8. Change template replaces the objects of a matched layout with the template's (D1539, confirmed by the owner 2026-11-24), and a matched
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


# Patch 3 — templates in the web app, the menus and the E2E (D1540)

Patches 1, 1b and 2 are assumed applied. Test seams, confirmed by the owner: lib modules (pure functions, vitest), the
menu manifest, and the E2E scenarios of `templates.feature`.

## What was built

* **Server** — `template_change_preview(template)`, a read method (D1540): ten counts, from the same plan the change
  uses, changing nothing (`claudia_creates.preview_change`). The list of a template's layouts names only those a person
  can choose (CODE-90).
* **Web libs** — `templates.ts` (cards, labels, `startFromTemplate`), `admin-templates.ts`, `template-change.ts`
  (summary lines, the note's checks, the languages), `template-menu.ts` (the Format ▸ Template submenu), and the
  admin API calls and the session methods `changeTheme`, `changeTemplate`, `templateChangePreview`, `saveAsTemplate`.
* **Web UI** — `AdminTemplates.vue` (Server settings ▸ Templates: list, Add template… with a check before anything is
  added, Remove), `NewPresentationDialog.vue` (the cards of a new presentation), `ChangeTemplateDialog.vue` (Theme
  only / Theme and layouts, the template, the counts, Change, Cancel), `SaveTemplateDialog.vue` (name, language, what
  it is for, Save file…).
* **Menus** — Format ▸ Template ▸ Change Theme…, Change Template…, Save as Template… in the manifest of the three
  apps' shells (web, Linux, Windows/macOS), `claudia-menus.xlsx` rows 97–99, `keyboard-shortcuts.md`.
* **i18n** — 55 German strings; pot, po, pseudo-locale, both `.mo`, the web catalog.
* **E2E** — `tests/e2e/specs/test_templates.py` binds `templates.feature` (no longer `@draft`): 6 of the 8 `@core`
  scenarios run in a real browser against a real server; the 11 `@extended` ones skip with "not automated yet".

## Assumptions

1. A new presentation asks which template only when the server has one besides Basic; with only Basic it is made at
   once, as before.
2. A template's language is shown in its own language ("Deutsch"), as the mock and the App Language menu do; the
   scenario "A template says in which language it is written" says "German". **Owner to decide** which is right. Basic
   is named in the language of the page.
3. **Keys, provisional:** Change Theme… Ctrl+Alt+Shift+U, Change Template… Ctrl+Alt+Shift+V, Save as Template…
   Ctrl+Shift+F12. The keys the owner chose (Ctrl+Alt+E, Ctrl+Alt+M, Ctrl+Alt+Shift+M) are types of AltGr on German
   keyboards, which the manifest test forbids. The owner is asked to confirm or choose others.
4. Change Theme… and Change Template… are disabled for a reader; Save as Template… is always enabled (it is an export,
   which a reader may make).
5. Change Theme… opens on "Theme only", Change Template… on "Theme and layouts"; the person can switch in the dialog.
6. The template file is saved by the browser's download, named by the server (`<slug>.claudia-export.zip`).
7. The dialog's counts are sentences ("1 style replaced · 1 style added"), and a scope that does nothing says "stay as
   they are" instead of "0".
8. A presentation made from a template does not announce a file ("… is here. The file was not kept") (CODE-91).

## Review (two reviewers, standards and spec) and what was done

Fixed: strings the extractor missed (`tr(` → `t(`; 9 new German strings), plural wording ("1 are unchanged"), the Add
template dialog now names the file's language and layouts (the @extended scenario "A template is a file anybody can
check…"), `Change theme`/`Change template` summaries are two functions instead of one with a mode argument, the
admin and the dialogs share `MAX_NAME`/`MAX_PURPOSE`, native browser validation texts are off (`novalidate`; our
own sentences are shown), the scope toggle of Change template answers the arrow keys, a sleep in the E2E is gone,
`_matched_layouts` is typed, the orphan sample script is removed.

Left, as judgement calls: the CSS of `.hint`, `.error` and `.buttons` is repeated in three dialogs as in 25 other
components (no shared class exists); `OpenDialog` has `enter(session, announce)` as a flag (CODE-91); `currentLocale()`
(front page) and `languageNow()` (inside a document) both give the locale of a request, as elsewhere in the app;
"twelve slides with text" are twelve slides with speaker notes in the E2E (no menu makes text boxes on a slide from the
outside yet), so the text and picture claims of "Saving a presentation as a template…" are checked only through the
file's parts and the notes.

## Mock M and the mocks: what is not built

* Format ▸ Template does not say which template the presentation came from (@extended "A presentation says which
  template it came from"; the `template` method answers it, no view shows it).
* "Show the slides…" in the Change template dialog (the preview counts slides, it names none; D1540).
* Thumbnails of the layouts on the cards and in the dialog.
* The step "What would you like to achieve?" in front of the choice between Change theme and Change template.

## What could not be run

* The GTK client with real GI (no PyGObject here): its manifest and the generated GMenu XML are tested without it; the
  menu was not seen in a running Linux or Windows/macOS window.
* Two `@core` scenarios: "A presentation keeps no link to its template" and "Change template… also takes the layouts,
  matched by name". The product has no menu that changes a layout of a presentation or puts a slide on another layout
  (the layout editor is a later story), so their steps cannot be driven from outside. The 11 `@extended` scenarios have
  no step code yet.
* Firefox (the scenarios are not tagged `@firefox`).
* The `layout/` package needed `npm ci` in this workspace before its gate steps could run; they then passed.

## BITV

The cards are native radio buttons in a fieldset with a legend; the dialogs are the app's `Modal`; every control has a
text label; the preview is plain text. Not measured: contrast of the selected card, a screen reader's reading of the
card meta ("4 layouts · English"), focus order in the dialogs. These are checked in the BITV round, not here.


# Patch 4 — UX-76: keys typed in a dialog on the slide (D1541)

Reported by the owner on 2026-11-24, reproduced first (UX-76, size 1) and fixed on this branch. Seams chosen: the E2E
script `describe-creates.cjs` (what a person sees: nothing moves, nothing is deleted, the name is edited and saved) and
one pure function, `keysAreTheirs`, in vitest. Red before green: the script failed at "the arrow keys moved the text box
behind the dialog" and then at Backspace.

* `lib/key-owner.ts` — `keysAreTheirs(target)`: a field that is typed into, or anything inside a `<dialog>` or
  `[role=dialog]`. `SlideCanvas.onKey` returns early for it.
* `names.feature` — one scenario, `@core @app:creates @e2e:describe-creates`.
* `describe.cjs` (computes) — a check that Backspace and an arrow in the name field leave the picture alone (it passed
  before the fix: not affected).

Assumption: the other dialogs drawn inside the slide (Image properties) are covered by the same rule; they were not
driven one by one. Could not be run: Safari and a real Mac keyboard (the report said "on a Mac"); the key events are the
same in Chromium, which is what was driven.

