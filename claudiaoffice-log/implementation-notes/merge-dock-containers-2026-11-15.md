# Merging `dock` and `containers` into main (2026-11-15)

`file-handling` needed no merge: main already holds it, put there by hand as `c87590b` ("Improved file handling merged to
main"), with its decisions renumbered from D520–D525 to D530–D535 because `search-ui` had taken D520–D522 first. The
branch's own history was never merged, so merging it again only produces add/add conflicts in every file it touched.
Delete the branch.

`dock` and `containers` both still gave themselves D520 and up, which on main belong to `search-ui` (D520–D522) and
`file-handling` (D530–D549). Both were renumbered while the patches were made, not by hand afterwards:

| Branch | Decisions | Now | Stories | Now |
|---|---|---|---|---|
| `dock` | D520–D523 | D550–D553 | E5.18 replay, E5.19 tags | E5.19, E5.20 (E5.18 is `file-handling`'s) |
| `containers` | D520–D524 | D560–D564 | none | none |

The renumbering rewrote every mention, in the decision files (names and front matter), the stories, the code, the tests
and the changelogs, and only the lines the branches wrote themselves. `tests/test_decision_log.py` passes.

## Where the branches touched the same things

* **Web sessions and menus** (`base-session.ts`, `slide-session.ts`, `DocumentFrame.vue`, the three workspaces): both
  add state, events and menu entries. Kept both. `lookOnly` (dock) replaces the viewer test in `DocumentFrame.vue`
  because it is true for a viewer and for a replay.
* **Catalogs**: `po/`, the `.mo` files and `de.json`/`xx.json` are generated, so none was merged by hand: the template
  is extracted again, the German of main, dock and containers is put together (no string differs between them),
  then everything is compiled. A merge that keeps one side's `po/de.po` loses the other side's translations.
* **Changelogs**: dock's and containers' entries are under `[Unreleased]`; no version was changed.

The three branches' commits that were not on main: `dock` e459c42, 72913b1, 022d883; `containers` fa2de98.
