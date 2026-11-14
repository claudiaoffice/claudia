---
id: D1010
title: "A workbook's print setup: two commands, three wire methods, and what the bar's choices are"
status: current
applies-to: computes
date: 2026-11-14
round: "Printing sheets: the computes print preview (E6.19, branch computes-print)"
supersedes: []
superseded-by: []
---

# D1010 · A workbook's print setup: two commands, three wire methods, and what the bar's choices are

**The workbook holds one page (`SetPrintPage`: paper, orientation of the paper, margins, page numbers) and one sparse `SheetPrintSetup` per sheet or chart tab (`SetSheetPrint`); both are steps in the history with exact inverses, so printing is undone and redone like anything else (D904, D917).** The wire has `print_setup` (everything, defaults filled in), `set_print_page` and `set_sheet_print`; the assistant and viewers may not change them (`people_only`, D63). The language of the workbook is the shared `language` / `set_language` pair every app has.

**In the preview, Contents (sheet, selection, whole workbook) is the choice of whoever prints, not a step in the history, so a viewer makes it too; Scale and the sheet's orientation are the setup and need the right to change it.** With a single sheet shown, Portrait and Landscape in the bar change that sheet (D1004); with the whole workbook they do not apply, since each sheet lies its own way. A chart tab has no scale: it fills its page (D1008). The selection is offered only when more than one cell is selected.

**Notes.** Supersedes the wire names of the story list (`set_print_setup`): two methods, because the page and the sheets are changed independently and by different people. Repeat rows and columns are stored as numbers and do not yet follow structural edits (rows inserted above them); a later story gives them the treatment names have (E6.5). A server from before this decision answers `unknown_method`; the preview then prints on the default page and offers no changes.
