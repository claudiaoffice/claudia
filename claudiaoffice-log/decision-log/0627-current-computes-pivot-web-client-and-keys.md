---
id: D627
title: "The pivot table in the web client: what was built from the approved mocks, and the keys that replace the proposed ones"
status: current
applies-to: computes
date: 2026-11-15
round: "Pivot tables (branch pivot)"
supersedes: []
superseded-by: []
---

# D627 · The pivot table in the web client: what was built from the approved mocks, and the keys that replace the proposed ones

**The four mocks of D624 are built in the web client, and the keys of D624 are replaced, because three of them cannot work.** The manifest's own test (`test_no_key_is_one_a_browser_keeps_or_alt_gr_types`) refuses Ctrl+Alt+T (the terminal on Ubuntu) and Ctrl+Alt+E, M and Q (AltGr+E, M, Q type €, µ and @ on a German keyboard, and on Windows Ctrl+Alt is AltGr). Every free Ctrl+Alt letter is taken or refused, so the keys are:

| Entry in Tools | Key (proposed in D624) |
|---|---|
| Pivot Table… | Ctrl+Alt+V (was Ctrl+Alt+T) |
| Pivot Fields (show or hide the panel) | Ctrl+Shift+Alt+F (was Ctrl+Alt+M) |
| Value Field Settings… | Ctrl+Alt+Z (was Ctrl+Alt+E) |
| Show Pivot Table as SQL… | Ctrl+Alt+X (was Ctrl+Alt+Q) |
| Delete Pivot Table… | Ctrl+Shift+Alt+V (was Ctrl+Shift+Alt+E) |

The five entries are in the one menu manifest (`clients/linux/src/claudia_shell_gtk/manifest.py`), so the web page, the GTK client and the generated menus of the macOS and Windows clients show the same key (`notes/keyboard-shortcuts.md`). The last four are off while the cursor is not in a pivot table (Pivot Fields stays on while its panel is open, so it can be closed).

**Built as in the mocks:** *New pivot table* (name, source preselected from the cursor, a new sheet by default or a cell of this one); the field panel (floating and movable, source, field list with ticks, the four boxes with chips, a ▾ menu on every chip with *Move to …*, drag between boxes, the two total switches, a line saying what it fills and when something is wrong); *Value field settings* (name, five ways to summarize); *Pivot table as SQL* (read-only, Copy SQL, *Convert to SQL query…* as one undo step); *Delete Pivot Table…* asks first. The same entries are in the cell's right-click menu inside a pivot. The panel follows the server: a change is shown at once and sent as `update_pivot`, and dropped again if the server refuses it.

**Built, but different from the mocks:**
- **No number format in Value field settings, no preview.** A value field has no format of its own (D626: the grid is plain values), so the mock's *Number format* and *Preview* are left out until there is a place to keep one. A cell of a pivot takes its format from its own style like any cell (an average shows many decimals until the person formats the cells).
- **Filters are chosen in a dialog from the chip's ▾ menu** (*Choose members…*), not as a `(All) ▾` cell above the table on the sheet: the pivot's cells are what the engine gives, and nothing else is drawn on the sheet. A field with more than 40 different members cannot be filtered by a list yet (the members come from the same read-only preview as the SQL editor, which shows 50 rows at most) and the filter keeps them all.
- **One row field and one column field** (D621): putting a second one into a full box sends the first back to the list, and the person is told.
- **Cell roles are drawn under the cells**, like a table's tint (header, labels, totals), and a header or total is also set in bold, so no meaning rests on colour alone; a cell of a pivot says what it is when the cursor is on it (live region, for screen readers).
- The mock 4 text "the cells stay as they are" is true only for a pivot without a column field (D626); the dialog says "with one header row".

**Also.** The pivot is made with the words of the person's language (`pivotLabels()`), kept in the pivot (D622). The web client asks for `pivots` again after a `pivots` event and after any change of cells or rows while the workbook has a pivot, one request at a time (more asks that come while one is out are one more ask). A server from before pivot tables is opened without them. *Not built:* number formats, "show values as", more than one row or column field, the filter dropdown on the sheet, a Help topic, GTK-specific drawing (the Linux client shows the web page; the menus come from the manifest), a Firefox check, component tests (vitest here runs without a DOM; the panel and dialogs are covered by `web/e2e/pivots.cjs`, the rules by `web/tests/pivots.test.ts`).

**D623 (a pivot is live, no Refresh) was flipped to current when it was built in step 2, not on an explicit answer; say so if you want it the other way.**
