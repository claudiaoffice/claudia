# Merging `import-export-wiring`, `rotation-ui` and `pivot` into main (2026-11-15)

The three branches were put on main as patches, in that order (oldest first; `rotation-ui` had to meet the wiring's own
rotation step in odp and pptx). Each branch's commits come first, then a "Merge fixups" commit, then "Generated files"
(catalogs, `.mo`, `de.json`/`xx.json`, the key table, the generated menus, the API snapshots: made again by their
scripts, never merged by hand; the German of each branch is carried over). Then the fixes that only the merged tree
showed.

## `dock`

Integrated already: main holds its three commits as `d73af5c`, `489554b` and `3a8a29c` (see
`merge-dock-containers-2026-11-15.md`), renumbered D520–D523 → D550–D553 and E5.18/E5.19 → E5.19/E5.20. Every line it
added is on main, in places worded again by the QA of 2026-11-15. Delete the branch.

## `import-export-wiring`

Its "Intermediate merge from main" (`491a9f7`) is a squash with one parent, so git did not know that main (`50beb2b`)
was in it, and main itself holds the branch's first commit as the squash `be08ce8`. The branch's own commits were taken
one by one (`0574958`, `ecfb45d`, `3471477`, `9d619e3`, `dfe66bd`, `c5bb115`); `491a9f7` and the empty `19d3d50` were
left out. `c5bb115` also held `dock-containers.mbox`, a patch file of the earlier merge, at the top of the tree: left out.

| Package | Branch | Now | Why |
|---|---|---|---|
| claudia-core | 0.24.0 | 0.26.0 | main had 0.25.0 |
| claudia-computes | 0.8.0 | 0.9.0 | main and the branch had both made a 0.8.0 |

## `rotation-ui`

Both branches turned objects in odp and pptx (D459 and D1021–D1022), with the same arithmetic. Kept: the shared
helpers of `claudia_odf_io.transform` and the pictures of the wiring; from rotation-ui the outline rule (D1022: on
import too, in odp's probe as well, so that import and insert judge alike) and a patch that writes only the attributes
that changed. `draw:transform` carries the angle to 15 significant digits, the text LibreOffice writes. Both had given
`XmlPart.set_attributes` a `remove`: rotation-ui's keyword-only one is kept (claudia-odf-io 0.6.0, **Breaking** for a
positional caller; there was none). pptx had `_turn` twice and called it twice per object.

| Package | Branch | Now | Why |
|---|---|---|---|
| claudia-core | 0.26.0 | 0.27.0 | the wiring had 0.26.0 |
| claudia-creates-io | 0.5.0 | 0.6.0 | the wiring had 0.5.0 |
| claudia-composes | 0.10.0 | 0.11.0 | the QA of 2026-11-15 had 0.10.0 |
| claudia-odf-io | – | 0.6.0 | the two `remove`s became one |

Found on the way, the branch's own: three test files called `test_turned_objects.py` (pytest stopped at collection),
an `<input/>` the web lint refuses, two lines too long for ruff, and `BlockAnchor.floated_to`, used nowhere. Two tests
of the wiring and of main moved to D1022 and to anchors with `dx`/`dy`.

## `pivot`

| Package | Branch | Now | Why |
|---|---|---|---|
| claudia-computes | 0.8.0 | 0.10.0 | after 0.9.0 (D462) |
| workbook state schema | 13 | 14 | names with ids (D552) had taken 13 |

Three of pivot's keys were taken on main: Ctrl+Alt+Z (View ▸ Replay, D551), Ctrl+Alt+X (Edit ▸ Reference, D551) and
Ctrl+Shift+Alt+F (Insert ▸ Container ▸ LaTeX, D560). Value Field Settings… is Ctrl+Shift+Alt+U, Show Pivot Table as
SQL… Ctrl+Shift+Alt+Q and Pivot Fields Ctrl+Shift+Alt+M now (D627). The third was not seen by the manifest's test,
which compared accelerators as text (`<Primary><Alt><Shift>f` and `<Primary><Shift><Alt>f`); it compares chords now.

"On a new sheet" named the sheet after the pivot, which D552 refuses (a sheet may not be named like a range, and the
pivot's result is one). The sheet is called "Pivot", as in mock 1, numbered while the name is taken.

## Checked

`uv run python scripts/check_debt.py` clean (claudia-composes back over its floor of 97 %, which the wiring had raised
on its own tree, with two tests of paragraphs as things); the CI e2e job's scripts in Chromium, against main and the
merged tree: the same results, `e2e:pivots` passing, `e2e:print` failing on both only for the fonts CI fetches.
The GTK tests of the Linux client need a desktop and were not run (its manifest tests were).

Not done here: D625 (a pivot in xlsx and ods) stays undecided, so a pivot is not yet written to Office or OpenDocument
files.
