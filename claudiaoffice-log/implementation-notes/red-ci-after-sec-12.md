# The red CI after SEC-12 (2026-11-21)

Branch: `main` (the owner asked for the merge and for the failing tests to be fixed). Bugs: UX-56, UX-57, UX-58, UX-62,
PROC-38, PROC-41, PROC-42, PROC-43. Decision: D1390.

## What was red, and why

| Job | Since | Cause |
|---|---|---|
| Python (Linux, Windows, macOS) | the test was written | PROC-38: the hash of the test took 0.12 s on the runners, 0.15 s was needed |
| End to end (Chromium) | 2026-11-17 | a chain: the Python E2E step, then `objects.cjs`, behind which the other scripts had not been seen in CI for days |

I ran the whole job on one computer in the order of `ci.yml`, with the fonts and hyphenation patterns CI fetches, and fixed
what came up. `./run-e2e.sh` was not used: it runs the specs, and the red steps are the older scripts.

## Fixes in the app (each found by `objects.cjs`)

1. **`SheetGrid.vue` — the handles' wrapper stops `mousedown`** (UX-57). The handles are drawn beside the object; their
   `mousedown` reached the cell selection, which let go of the object and selected cells.
2. **`SheetGrid.vue`, `SlideCanvas.vue` — keys from a `role=dialog` inside them are the dialog's** (UX-56). The Rotate by…
   popover sits inside the element that listens for keys; Backspace there deleted the object, Enter began an edit.
3. **`TextContainers.vue` — a press on an object is the object's** (UX-58): `preventDefault` on the pointer down, unless its
   words are being written.
4. **`TextContainers.vue` — ← and → nudge by `NUDGE` (10), Shift `NUDGE_FINE` (1)** (UX-62, D1390). One constant in
   `lib/geometry.ts` for composes and creates.

## Fixes in the tests and the workflow

- `test_server_password_methods.py`: the cost is `calibrate(...)` with the old cost as floor (PROC-38).
- `tests/e2e/test_computes_grid.py`: the launcher's process group is killed (PROC-41).
- `ci.yml`: the Fonts step reads the setup code from the state folder (PROC-42, my SEC-12 change had missed it).
- `objects.cjs`: four stale lines, made right by the contract (PROC-43), and one new check (Backspace in the angle field,
  red without fix 2). Run six times in a row.

## Assumptions

- The nudge of 10 units in composes (D1390) was not tried against a real page.
- A "shape without an aspect" is judged by the handles it shows (no edge handles = keeps its proportions): the contract
  ties the two together.
- The commits go to `main` and `backlog` directly: the owner's instruction ("fix the failing tests") came after the merge
  and named no branch; the project rules say to fix main until CI is green.

## What could not be run here

Firefox, the GTK window tests (no GTK in the sandbox), Neutralino itself (its shell page and core run faked, as in CI), a
screen reader. The workflows `deb`, `windows`, `docker`, `codeql` and the demo deployment run on GitHub only.
