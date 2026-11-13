# The accessible grid and alt text on `bitv` (2026-11-13)

Follows `bitv-scorecard-2026-11-13.md`: the two items it named as the largest remaining gaps, built on branch `bitv`
(UX-02 and UX-31 in the bug tracker). Built before the screens were agreed, against the project rule; the mock-up
`mockups/describe-object-and-grid-structure.svg` shows what was built so it can be confirmed or changed.

## The grid for a screen reader

**Structure.** The grid is virtualised and drawn by absolutely positioned elements, so ARIA carries the structure the
DOM does not. Each drawn row is a zero-height `role="row"` wrapper in the stage (static, so the cells keep their
coordinates relative to the stage); it holds the row number (`rowheader`, `aria-colindex` 1) and the cells that have
content. The column letters are the one `row` with `aria-rowindex` 1. The sheet's extent is said by `aria-rowcount` and
`aria-colcount` (the header row and column count), so a reader can say "row 3 of 10001" while only some 60 rows are in
the page. Layers that only paint (table frames, gridlines, the corner) are hidden from the reader.

**Focus.** Focus never leaves the grid element; `aria-activedescendant` names the active cell. That cell is therefore
always an element, also when empty, and exists only in the active row's wrapper; when the active cell scrolls out of the
drawn window or is being edited, the attribute is left off rather than pointing at nothing. Only the active cell has an
`aria-label` ("B2, 9600, formula"): naming all 1,500 drawn cells would have cost a string build for each on every scroll
and says nothing the text does not.

**Words.** `web/app/lib/grid-a11y.ts` holds them as plain functions, tested without a browser
(`web/tests/grid-a11y.test.ts`): the active cell's name, the announcement for a range ("A1:B2 selected, 4 cells", "Column B
selected"), the index arithmetic. What colour, shape and dots say to the eye (a cell's part in a followed computation, the
dots of a result of alternatives, an error and why) is said in words too.

**Live region.** `Workspace.vue` keeps one polite `role="status"` beside the grid (not inside it, where a status is not
an allowed child). It says a range, a whole row or column, or a selected object ("Selected: Picture: …") 300 ms after the
selection stops changing, so a drag says its final size once.

**Layering.** The row numbers moved from a clipping container into the row wrappers; their stacking is now by z-index
(row numbers 2, column letters 3, corner 4), which gives the look the clipping gave. Worth a visual check in a real
session at several scroll positions; the e2e does not compare pixels.

**What axe found.** On the computes page the grid itself had nothing to fix. The rest of the page had: the sheet tab list
held the "new sheet" button, the Draw button's name did not contain its visible text, and two texts were under 4.5:1 (the
history panel's times, the revision label). Those are fixed. Landmarks are not (UX-32): axe lists them only as best
practice.

## Alt text and decorative objects

One model for all apps: `ObjectBody.description` and `.decorative` in `claudia_core`, a command `DescribeObject`,
`AddObject` at schema 2 with an upcaster from 1 (an old log replays: the description is the import's alt text), model
`state_schema` bumped in computes, creates and composes (a snapshot of the old shape is rebuilt from the log). The server
refuses a picture with neither words nor the mark; anything else may go undescribed, because the AI and old documents can
leave it so. The dialog, the menu entry, Ctrl+Alt+D and the decorative box at import are the web page's; the native shells
get the entry from the Linux manifest (`clients/linux/src/claudia_shell_gtk/manifest.py`) and the generated Windows/macOS
menus, and open the page's dialog (the page owns it, like Apply Style…).

Export: PPTX and ODP write the description; PPTX also writes the decorative extension. The extension's URI and
namespace are written from memory and **must be opened in PowerPoint** before anyone relies on them. ODF 1.3 has no
decorative attribute: the export reports it as a loss rather than writing one a reader may reject. Import of descriptions
from those formats, and ODS/XLSX floating objects, are not built.

## Left open

- No screen reader was run. NVDA/Orca/VoiceOver scripts belong in the release checklist (E5.10).
- Other people's and the AI's changes to cells are not announced.
- Whole-column selection marks only the drawn cells `aria-selected`.
- Composes has no objects, so nothing to describe there yet; its images will need the same fields when they exist.
- Chart tabs have a name but no description.
- D233 (the accessibility standard) is still undecided.
