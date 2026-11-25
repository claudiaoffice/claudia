# Implementation note: bug eater, batch 2

Written 2026-11-25, branch `batch-2` (from `main` at `e5bb76fa`). The brief is `notes/bug-eater.md`, the queue
`notes/bug-eater-queue.md`. No decision of its own yet (the next free id is D2004). One commit per item, its message
starting with the item's ID. This note grows with the batch; what is below is done.

## What changed, per item

| Item | Change | Test written first (seen red) | Escaped because |
|---|---|---|---|
| PROC-22 | The LibreOffice job of CI is no longer `continue-on-error`, and its log names LibreOffice's version | `tests/test_ci_workflow.py`, `tests/test_odf_libreoffice_check.py` | missing test |
| PROC-59 | CI job `e2e-firefox` runs the `@firefox` scenarios in Firefox | `tests/test_ci_workflow.py::test_ci_runs_the_firefox_specs_in_firefox` | missing test |
| PROC-40 | `document-file/requirements.feature` and `invariants/objects-in-composes.feature` are bound (12 of 13 runs pass; the table's description waits as `@pending:UX-85`) | the scenarios themselves | missing test |
| UX-76 | The New sheet dialog offers the next free "Sheet<n>" in the person's language, past every name in the workbook | `web/tests/tags.test.ts`, `web/tests/session.test.ts` | spec gap |
| UX-84 | Selecting an object locks it in computes and composes too (D1223), and a colleague's selection is drawn in the three apps by one component | see below | missing test |
| PROC-29 | Step 1b of the object battery: what a second window sees of a selection, for every kind in every app | `web/e2e/objects.cjs` | missing test |

## UX-84: one lock for a selected object in the three apps

- `BaseSession.lockObject(id, holder?)` locks the selected object (`lock` on an `ObjectSet` of its holder), or only shows
  it for somebody who may only look. `null` unlocks, and the others then see the person where she rests
  (`restingRegions`): nowhere in creates and composes, and on a computes sheet her cells (`Session.show` keeps the last
  ones). On a slide of a workbook she rests nowhere, as in creates.
- `holdRegions` counts a lock as held from the moment it is asked for, so letting go before the answer still unlocks.
  Requests keep their order on the one connection.
- Creates' and computes' `SlideActions` use `lockObject` through `SlidePort` (`show`, `hold`, `release` and `looking`
  are gone from the port).
- Computes: `SheetGrid.vue` locks with its own sheet whenever `selectedObject` changes, and lets go of the object when
  another sheet is shown, when the object is removed, and when the grid goes.
- Composes: `TextSession.selectObject` is async and locks. A new object is locked at the paragraph it was put in, before
  the server has told of it. A selected object moved to another paragraph is locked there again, since the lock names
  the paragraph. One that a colleague removed is let go of. While an object is selected the words round the caret are
  not held, since holding them would replace the object's lock. They are held again once no object is selected.
- `OtherOnObject.vue` draws a colleague's selection (her colour round it, her name above it, the existing
  "{user} is working on this" / "{user} selected this" as its title) in `SlideCanvas`, `SheetGrid`, `TextObjectLayer`
  and `TableView`. `othersOn` and `Other` moved from `slide-host.ts` to `objects.ts`, because all three apps use them now.

**Tests:**
- `web/tests/session.test.ts` and `web/tests/text-session-objects.test.ts`, describe "… locks it, as in creates (D1223)".
  They cover locking and unlocking, a colleague who has it locked, unlocking before the answer, a slide in a workbook,
  a move to another paragraph, a removal by a colleague, and the caret's words.
- `web/tests/text-object-layer.test.ts`: a new picture is locked at its paragraph.
- The object battery's step 1b (PROC-29) runs 12 times: computes picture, chart and container; composes text box, shape,
  picture, container and table; creates text box, shape, picture and container. Ben sees ann's colour (the colour of
  her own avatar) round the object and her name. His drag is refused (for a table, his Delete), he is told so, and his
  window shows the object where it is. Nothing reaches ann's history. When she lets go, her name goes. Ben's view is
  kept as `objects-<app>-<kind>-watched.png`.

**Assumptions:**
- On a table the name sits inside its frame, at the top right. The frame scrolls sideways (`overflow-x: auto`), so a
  name above it would be cut off.
- Selecting an object locks it even while the person only clicks, as in creates. A colleague who tries to select it is
  told and does not get it.
- In composes a colleague can be seen briefly nowhere when she lets go of an object. She is seen at her caret again
  `PLACE_MS` later.

**Not covered:**
- A lock on a table does not stop a colleague writing in its boxes: those changes lock a `TableRegion`, not the
  object. The table's own changes (move, delete, name, options) are refused.
- A colleague's name in row 1 of a sheet is under the column header (UX-86, also true of cell outlines before).

## Say what could not be run

- Firefox (PROC-59's job): it cannot be downloaded in this workspace. CI's first run is the check.
- The GTK and Neutralino windows: both load the web app, so they get UX-84 with it. There was no hand check (PROC-30).
- A screen reader. The outline and the name are `pointer-events: none`, carry no role, and are not read out (as in
  creates). The title says who has the object.
