# Deleting and hiding styles (E1.10, D226, D780–D786)

What was built, where, and why it looks like this. Branch `style-delete`. Kernel, server and the web client are built (D783, D786); the desktop shells open the page's own dialog.

## The rule

A deletion never leaves a dangling reference (D226). There are two ways (`DELETE_HOWS`, D785), in the order the dialog shows them, both with a `target` style of the same kind (never the style itself or one based on it):

* `assign` (default): users get `target`; children are re-based on `target` unchanged, so **looks change** (`assign_changes_look(model, style, target)` tells the dialog whether, so it can count first). No stand-in. The dialog preselects `StyleBook.fallback(style)`, the plain style of the kind, which is what "no style" means.
* `rebase` holds every look: children move under `target` and say what differs, users go to a stand-in "<name> (kept)" under `target`.

`target` may be left out only when nothing has the style and nothing is based on it. D784's third way (*keep their look*, the style's own parent) was dropped: it was a rename.

## Kernel (`packages/claudia-core/src/claudia_core/styles.py`)

* `StyleDef.origin` (`document` / `builtin` / `template`) and `hidden` (D780). Written only when not the default, so old documents load unchanged. The three apps mark their built-ins in the `_style` helper of their built-in list.
* `plan_delete_style(model, style_id, *, how="assign", target=None) -> Batch`. Planned against the document as it is, applied as one batch (all or nothing, one undo step). Steps: `CreateStyle` of the stand-in (only if something has the style itself), a `RebaseStyle` per child, the model's `restyle_users(old, stand_in)` commands, `RemoveStyle` last.
* `held_look(old, base)`: the properties a style must set itself to look as `old` under a parent that looks as `base`. `INITIAL_CSS` (`css.py`) gives the value of "nothing" for the properties where it is the same in every app; the rest (font, size, colour, `text-align`, `hyphens`, `vertical-align`, `fill`, `stroke`, `stroke-width`) refuse, naming the property (D781). The same for heading level, numbering and number format (`_own_settings`).
* `RebaseStyle` (parent + own CSS/number format/heading/numbering in one step; its inverse is itself with the old values) and `SetStyleHidden`.
* `StyleBook.rebase` refuses a cycle and a parent of another kind. `StyleBook.to_data` writes a parent before its children whatever order styles were re-based into, because `from_data` adds them one by one; in memory the order is the one a person sees in a menu. `CreateStyle.before` and `StyleBook.add(before=)` put a style back where it was, so the undo of a deletion restores the list exactly.
* The collision rule (D782) costs nothing extra: `RemoveStyle` is the last step and is refused while anything has the style, which rolls the batch back.

## The apps

`restyle_users(old, new) -> list[Command]`: `ObjectModel` (objects and their words: `SetObjectStyle`, `SetParagraphStyle`), `TextModel` adds paragraphs (`SetStyle`), `WorkbookModel` adds style ranges (`SetCellStyle`, one per range, through `CellStyles.ranges_named`). A model that says a style is in use (`style_in_use`) and has no `restyle_users` cannot delete it, and says so.

## Server (`packages/claudia-server/src/claudia_server/styles.py`)

`style_deletion` (read, viewers may ask): uses, children, `suggested` (`id`, `name`: the plain style) and the targets, each with `changes_look` (assign) and `holds` with a reason (rebase). `delete_style` (`how`, `target`) and `hide_style` (write). They are not on the assistant's lists (D782).

## Checked

Tests: `packages/claudia-core/tests/test_style_deletion.py` (the algorithm, hiding, two authors), one file per app for what has a style, `packages/claudia-server/tests/test_server_style_deletion.py` (the wire).

## Web client (`web/`)

* `lib/style-deletion.ts`: the logic without a view (`DeletionChoice`: which way, which target, whether it may go; the sentences; the row access keys). Tested in `web/tests/style-deletion.test.ts`.
* `StyleHost.deletion` (optional): a host without it shows no Delete/Hide. The three hosts (text, cell, object) get it from their session (`deletionHost`); `BaseSession` has `styleDeletion`, `deleteStyle` and `hideStyle`; `TextSession` adds the document's step handling.
* `components/DeleteStyleDialog.vue` (the confirmation) and `StylesDialog.vue` (buttons, *Show hidden styles*, the announcement). `galleryFor(..., current)` and `formatItems` drop hidden styles (`pickable`).
* Browser check: `npm run e2e:style-delete` (needs the composes server on 8766).

## Desktop shells

Nothing to build: *All Styles…* is a page action (D301). Only its description in `clients/linux/.../manifest.py` changed; the neutralino menu files are generated and did not change.

## Not done, on purpose

* Upcasting of dropped properties: not wanted before the first release (D308).
* A command to define a colour role of one's own: it belongs to the colour axis (D200–D202), not to the style model; to be its own story.
* Re-basing is refused when the look needs font, size, colour, alignment and the like: there is no neutral value to write (D781). Open question to the owner.

## For the next agent

Do not delete a style by `RemoveStyle` alone: it refuses while anything uses it, on purpose. Do not move what has a style by hand: call `plan_delete_style`.
