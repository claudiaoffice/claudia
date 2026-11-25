# E10.27 Edit this layout… and New layout…: architecture

Proposal of 2026-11-25, for the owner to agree or change. Story: `Projects/claudia-office/_tasks/e10.27-edit-this-layout.md`.
Mocks (approved 2026-11-25): `mockups/creates-layouts-editor.svg`. Diagrams: `mockups/creates-layout-editor-architecture-1-packages.svg`
(where things go), `-2-classes.svg` (what is new), `-3-flows.svg` (three flows).

## What the code has and has not (read on 2026-11-25)

* **The model has it all but one command.** A layout is a holder of ordinary objects (`objects_on(layout_id)`); a placeholder is an
  object on it whose `SlideAnchor.purpose` is set (D1532); `layout_objects_of(slide)` returns the layout objects that are not
  placeholders; `DefineLayout`, `RenameLayout`, `HideLayout`, `MoveLayout`, `SetSlideLayout`, `RemoveLayout` exist with inverses;
  `settle` repairs the slides' bound copies after every command. **Missing:** a command that sets or clears the purpose of an object
  (a purpose only gets set at `AddObject` by plans and by template code, and the wire's `_on_slide` anchor builder drops it).
* **The server has no read of layouts and no write of them.** The `slide` read refuses a layout id. The events `layouts` and
  `slide_layout` are sent and nobody listens. The `snapshot` read carries layouts but the web page never calls it.
* **The web page knows nothing about layouts.** It draws nothing beneath a slide: `SlideCanvas`, the slide show (`SlideView`,
  `PresentShow`) and print (`print/source.ts`) show only the objects a slide holds. The PowerPoint and OpenDocument exports
  already draw layout objects (`objects_drawn_on`).
* **Presence exists** (`presence` method, regions): "others here" can be a region whose id is the layout.

## Where each piece goes, and why there

| Piece | Goes in | Why there |
|---|---|---|
| `SetPlaceholder(object, purpose)`, `DescribeLayout(id, purpose)` | `claudia_creates/layout_commands.py` | next to the six layout commands; one history, one undo |
| `copy_layout`, `mark_placeholder`, `unmark_placeholder` | `claudia_creates/layout_plans.py` | plans build a `Batch` of commands, as `delete_layout` and `update_layout` do; marking also gives or frees the slides' boxes |
| a built-in layout refuses changes to its objects | `SlideModel.check_anchor` and the commands' checks | the model refuses, as it does for a purpose twice in a layout; a client's check is only a courtesy |
| `is_empty` also true for an image without an asset | `claudia_creates/model.py` | one rule "empty means nothing a person put there", for every kind |
| `layouts`, `layout {layout}`, `new_layout`, `describe_layout`, `mark_placeholder`, `unmark_placeholder` | new `claudia_server/layout_methods.py` | sibling of `template_methods.py`; each ends in `done(ctx, Command, base)` |
| object methods take a holder | `object_methods.py`, `creates.py` | the parameters keep their names (`slide`) and the value may be a layout id, so old clients are not touched |
| `under` in the `slide` read | `creates.py` | canvas, show and print all use this read, so one field serves all three |
| layout rules without a page | `web/app/lib/layout-editor.ts` | pure functions, tested without a browser |
| editor mode, layouts, `under` | `web/app/lib/slide-session.ts` | the session owns state; components stay thin |
| band, panel, strip, two dialogs | `LayoutBand.vue`, `LayoutPanel.vue`, `LayoutStrip.vue`, `NewLayoutDialog.vue`, `BuiltInDialog.vue` | one component per thing on the mock |
| menu entries | `lib/layout-menu.ts`, `manifest.py`, regenerated `keys.generated.ts` and `menu.creates.json` | entries get ids and keys the way `template-menu.ts` does; the shells host the same page |

## Decisions to agree (they shape the code)

* **A1 – No new field in the document.** A text placeholder's hint is its own words: the layout's placeholder carries "Click to add
  text", the slide's bound copy starts empty, so only the layout shows the hint. Make placeholder on a text box therefore changes
  one thing, its purpose. A picture placeholder has no words, so its hint is a fixed word by kind ("Picture", in the person's
  language) and the panel has no hint field for it (the mocks B and G are redrawn so). Alternative: a `hint` field on `SlideAnchor`,
  a change of the document format with an export-format step, for one line of text.
* **A2 – A picture placeholder is an image object without an asset** (`ref` is `None`). The model does not forbid it, but the
  drawing, the exports, print and the slide show must skip it; checked and tested at the first TDD step. Alternative: a rectangle
  shape standing in for the picture, which would break "empty means empty" for pictures.
* **A3 – A placeholder added to a layout gives each slide that follows it an empty box; one removed frees them** where they stand
  (the same as deleting a layout, D1535). This is the least surprising reading of "changes apply to all slides at once", and what the
  other office programs do. Not covered by a scenario yet: it becomes one.
* **A4 – The object methods take a layout id in the place of a slide id.** A layout is a holder like a slide; this avoids a second set
  of methods for moving, sizing and styling.
* **A5 – `under` is added to the `slide` read.** It is additive; a desktop client that does not know it shows the slide as today. The
  slide show and print draw it from the first day, as the story says.
* **A6 – "n others here" is presence** with the layout id as the region, no new mechanism.

## What I have not decided and will check in the first TDD step

* Whether `settle` may change objects and emit `ObjectsChanged` for the boxes that A3 gives and frees (its docstring says it
  repairs; the note of 22 Nov already asked this).
* How much of print and PDF export draws `under` without a new drawing path.

## Seams for the tests (proposed, to be confirmed with the E2E list in step 5)

1. **Model:** commands and plans through `SlideModel` (marking, unmarking, copying, built-in refused, boxes given and freed).
   Catches the rules; misses the wire.
2. **Wire:** the six methods through the protocol with a real document. Catches parameters, `base`, events; misses the page.
3. **Pure functions** in `layout-editor.ts` (vitest). Catches sentences and refusals; misses the DOM.
4. **Browser E2E** `web/e2e/layout-editor.cjs` for the @core scenarios, creates server only. Catches the whole path; slow, so few.
