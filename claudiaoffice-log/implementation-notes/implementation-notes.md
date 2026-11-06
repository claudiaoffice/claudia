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

Not yet built: the web grid's variable row/column sizing, drag-resize of the header border, and the right-click
dialog (Patch 2 — `web/app/components/SheetGrid.vue` and new header/dialog components).
