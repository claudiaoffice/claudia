# Implementation notes: the menus (E5.23, E5.24), branch `menus`

Design: `notes/menus-architecture.md` (D1643–D1649). Scenarios: `specs/menus/menus-that-fit.feature`. One section per
slice of the build (§5 of the design).

## Slice 1 · The definition moves to `clients/contract` (D1643), 2026-11-25

No change of behaviour.
- `clients/linux/src/claudia_shell_gtk/manifest.py` became `clients/contract/src/claudia_menus/manifest.py`, with git's
  rename kept, plus a `pyproject.toml` (project `claudia-menus`, Python ≥ 3.12, no dependencies).
- The GtkBuilder part (`menu_xml`, `menu_elements`, `menu_button_id`) stays GTK's: it is now
  `claudia_shell_gtk/menu_xml.py`.
- `UnknownApp`, which the manifest took from the Linux client's `identity.py`, is now the definition's own `KeyError`.
  Nothing caught the old one from `for_app`.

What followed the move:
- **The Linux client:** `app.py`, `bridge.py`, `window.py` and eight test files import `claudia_menus`. `pyproject.toml`
  puts `../contract/src` on pytest's and mypy's paths and counts `claudia_menus` as first-party.
- **Start and package:** `start-linux-client.sh` puts `clients/contract/src` on `PYTHONPATH`.
  `packaging/debian/build-deb.sh` copies `claudia_menus` beside `claudia_shell_gtk` into `/opt/claudia/shell`, which the
  launchers already put on `PYTHONPATH`. `deb.yml` also runs on changes to `clients/contract/**`.
- **The generators and scripts:** `scripts/generate_keys.py`, `scripts/menu_audit.py`, `scripts/extract_i18n.py` and
  `clients/neutralino/tools/generate_menu.py` (and its mypy path) read the definition from its new place.
- **Generated files:** `web/app/lib/keys.generated.ts` and `notes/keyboard-shortcuts.md` were regenerated; only the
  path in their header changed. `po/claudia.pot`, `po/de.po` and `po/xx.po` were regenerated; only the `#:` places of
  the menu strings changed. The Neutralino menus (`--check`) are unchanged.
- **Vulture** looks at `clients/contract/src`.
- **The contract's README** describes the package.
- **One new test,** `test_the_definition_needs_nothing_but_its_own_folder`: a fresh interpreter with only
  `clients/contract/src` on its path builds all three apps' menus and loads neither GTK nor the Linux client.

Left as they were: notes, decisions, changelogs and bug entries that name the old path as history.

**Assumptions:** none about behaviour. The package's tests stay in the Linux client (see the design §3.1).

**Run:**
- the Linux client's tests on the system Python 3.12: 656 passed, 64 skipped (below);
- the root tests of keys, strings, catalogues, the audit and the specs;
- the Neutralino tool tests and `check-menu`;
- ruff, ruff format, vulture, and mypy for the Linux client and the Neutralino tools;
- the Debian build (`packaging/debian/build-deb.sh`): the package holds `claudia_menus` beside the client, and the
  computes menus build from the unpacked package.

**Not run:** the 64 tests that need GTK 4 and libadwaita, among them the window, the web page and the end-to-end test
of the Linux client. PyGObject cannot be imported in this workspace (a broken `gi` of the distribution), so no window
was opened and `window.py`'s new imports were not executed. The same tests run in CI under Xvfb.
