# Implementation notes

Short, per-feature notes written as the work happens. Status itself lives in `backlog.md`, derived from the code; a
note here never outruns the commit that proves its claim (PROC-03).

## Row height and column width (E6.16, D135) — Patch 1 of 2

Patch 1 is model, command, undo/history, serialization and the server RPC, with no UI change. Built and tested:
`packages/claudia-computes/src/claudia_computes/model.py` (`Sheet.row_heights`/`col_widths`, the `DEFAULT_ROW_HEIGHT`/
`DEFAULT_COL_WIDTH`/`MIN_*`/`MAX_*` constants, `Sheet.sizes()`, the `WorkbookModel.state_schema` bump to 2 and
`restore()`/`restructure()` changes), `packages/claudia-computes/src/claudia_computes/events.py` (`LinesResized`),
`packages/claudia-computes/src/claudia_computes/commands.py` (the new `ResizeLines` command, plus fixes to
`RemoveSheet.apply()` and `Structure.apply()` so undo restores sizes destroyed along with their lines — a real gap
the new state exposed, not introduced by it), `packages/claudia-computes/src/claudia_computes/__init__.py` (export),
`packages/claudia-server/src/claudia_server/computes.py` (`sizes`, `resize_lines`), and
`packages/claudia-server/src/claudia_server/apps.py` (`resize_lines` added to the AI's method allow-list).

Tests: `packages/claudia-computes/tests/test_sizes.py` (new, 24 tests: resize/undo, remapping across insert/delete,
redaction, `shifted_by` conflicts, serialization round-trip), plus additions to
`packages/claudia-server/tests/test_server_computes.py` and
`packages/claudia-server/tests/test_server_model_engine.py`. Full suite green at the time of the patch, run as
`uv run pytest` per package (a `conftest.py` name collision stops a combined run across packages — not fixed here,
out of scope for this patch).

Design: sizes are sparse per-line overrides on `Sheet`, mirroring the existing sparse-cells pattern — a line not
listed shows at the default. `ResizeLines` validates every index/size before changing anything (atomic, like
`SetCells`), carries no `regions()` (layout is not lock-gated), and its `redacted()` returns `self` unchanged — a
size is not secret content, the same stance already taken for `Structure` and `RemoveSheet`.

Known pre-existing issue, found but not fixed in this patch (out of its scope per CONTRIBUTING.md's "one idea per
PR"): `uv.lock.rej` is tracked in git at the original `main` HEAD (`558f429`), which trips
`test_repo_hygiene.py::test_no_rej_or_orig_files_are_tracked`. This predates Patch 1 and is unrelated to it.

Patch 2 (the web grid, drag-resize and the right-click dialog) follows below.

## Row height and column width (E6.16, D135/D160) — Patch 2 of 2

Patch 2 is the web half: variable-size rendering, the right-click header menu, the size dialog and drag-resize —
client-only, since Patch 1's `resize_lines`/`sizes` already take arbitrary per-line `[index, size]` pairs in one
call, which is exactly what scaling several lines by one percentage needs. Agreed first as four SVG mockups shown to
and approved by the owner (per the project's standing design-before-code instruction), reviewed in two rounds of
feedback — the first round was a misreading on the author's part (the live percentage belongs beside the drag's own
readout, not only in the dialog), corrected in the second, which also added the drag interaction itself.

Built and tested: `web/app/lib/line-sizes.ts` (new — the pure math: `buildSizeTable`/`offsetOf`/`lineStart`/
`indexAt` for converting between a line's index and its pixel position when most lines share a default and a few
don't; `percentChange`/`formatPercent`; `proportionalResize`, the D160 rule itself, including the clamp).
`web/app/lib/session.ts` (`State.rowHeights`/`colWidths`, `ensureSizes()`, `resizeLines()`, the
`rowHeight()`/`colWidth()` accessors, and handling the `sizes` event — plus forgetting a sheet's sizes, not only its
cells, on a `structure` event, since a structural edit remaps both the same way and the server does not echo the
remap back as its own event). `web/app/components/SheetGrid.vue` (reworked throughout: every place that assumed a
uniform row height or column width — `x`/`y`, `box`, `range`, `cellAt`, `reveal`, the cell/header templates, the
gridlines, which used to be one repeating CSS background and are now per-visible-line `<div>`s since a repeating
tile cannot draw uneven spacing — now goes through `line-sizes.ts`; plus the header-border hit-testing, the drag
gesture with its own live merged-in size while dragging, the live px/percentage tag, and the `headerMenu` event a
right-click on a header emits). `web/app/components/HeaderMenu.vue` (new — the right-click menu: insert/delete, text
only per the owner's feedback, and the row/column size item). `web/app/components/LineSizeDialog.vue` (new — the
dialog: the field, the live "+50%" tag, "Reset to default" as a link that only fills the field rather than
submitting, and the proportional-example footer for a multi-line selection). `web/app/components/Workspace.vue`
(wires the header menu and the dialog, mirroring how `StyleMenu`/`TextEditor`'s `style-menu` event is already
handled in `TextWorkspace.vue`).

Tests: `web/tests/line-sizes.test.ts` (new, 18 tests covering the size table, the index/pixel round trip including
inside a resized line, percentage formatting, and `proportionalResize` — the scaling itself, the single-line trivial
case, shrinking, and both clamp directions), plus additions to `web/tests/session.test.ts` (covering the default
before sizes load, loading once, following and reverting `sizes` events, forgetting sizes on `structure`, and
`resizeLines`'s own request/conflict handling). No new component-level tests: this codebase tests the pure `lib/`
logic and leaves `.vue` files as thin wiring over it (no existing component has its own test file either), so the
genuinely non-trivial logic — the size table, the index lookups, the proportional math — all lives in
`line-sizes.ts` and is covered there instead. `npm test` (300 tests) and `npm run typecheck` both green.

Design: the rule itself is D160 (`decision-log.md`) — scale by percentage anchored on the selection's top-most/
left-most line, never push every line to one pixel value; clamp a line the percentage would push out of range
rather than reject the whole change; only the border right after the anchor line resizes the whole selection when
dragged, any other border resizes just the one line it belongs to. The grid reflows live during a drag (not only
once the server answers) by merging the in-progress line's projected size into the same table the committed sizes
use, read from `props.session.rowHeight`/`colWidth` (the committed values) so the live preview and the eventual
`resizeLines` call are computed from the same baseline.

Known simplification, not in the mockups: a multi-line drag shows the live tag and the highlighted border only at
the dragged (anchor) line's own border — the mockups also show dashed/solid guide lines at every other affected
line's border moving as you drag. The resize itself is fully proportional regardless; only that secondary live
preview for the *other* lines' borders during the drag was cut for scope. A reasonable follow-up, not a correctness
gap.
