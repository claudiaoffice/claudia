# Menus architecture: one definition, judged in the page, drawn by every client

Stories: [[e5.23-menus-rebuilt-to-the-workbook|E5.23]] and [[e5.24-menus-that-show-what-fits|E5.24]] · branch `menus` ·
decisions D1640–D1659 · status: **agreed by the owner 2026-11-25 (D1643–D1649)**. Nothing is built.

Diagram: `mockups/menus-architecture-01-classes.svg` (iris: new, teal: changed, grey: kept).

## 1. The rule that decides where things go

**Each fact is in one place:**
- What the menus hold is one definition, as data. That includes each entry's place, key, and the rule for when it
  fits.
- Whether an entry fits is judged in one place, the page, which is the only part that knows the person's role, the
  selection and the document.
- The clients only draw what they are told.

The page runs inside every desktop window too. Judging there means the web app and the three desktop clients cannot
disagree about what fits. That is the definition of done's "web app and desktop clients do not diverge".

## 2. What I checked in the code

- **The desktop menus have one definition already:** `manifest.py`, then in the Linux client (`claudia_shell_gtk`), now `clients/contract/src/claudia_menus/manifest.py` (slice 1).
  - The GTK shell builds its menus from it.
  - `scripts/generate_keys.py` makes `web/app/lib/keys.generated.ts` from it.
  - The Neutralino menus (`clients/neutralino/src/generated/menu.*.json`) are made from it too.
- **The web builds its menus by hand.**
  - `lib/document-menus.ts` has 44 entries.
  - The three workspaces add theirs: `Workspace.vue` 36, `TextWorkspace.vue` 14, `SlideWorkspace.vue` 12.
  - `format-menu.ts`, `table-menu.ts` and `object-menu.ts` add more.
  - 55 `disabled:` expressions in the workspaces decide greying, each in its own words. A drift guard keeps the ids in
    step with the manifest. Nothing keeps the conditions in step.
- **A key belongs to a drawn menu entry.** `shortcuts.ts`'s `menuShortcuts` takes the keys from the menus the page
  draws. It skips a greyed entry, so the key falls through to the browser and nothing is said. A hidden entry would
  lose its key entirely, which contradicts D1604.
- **The shell contract** (`clients/contract/shell-contract.v1.schema.json`): `action_state` carries `enabled`,
  `checked` and `label` per action. There is nothing for hiding, nor for the "why" line of an empty menu. The contract
  allows new optional fields within v1.
- **GTK** greys through `Gio.SimpleAction.set_enabled`.
  - It already hides: the front page's short menu is `for_start(manifest)`, a filtered copy built into its own menu
    models (`window.py`, `_attach_menus`).
  - The page listens for its own keys (`KeyOwner.PAGE`), so a greyed GTK action does not swallow them.
- **Neutralino** rebuilds the whole menu on every state change (`menu-actions.ts`, `applyActionStates`). Leaving items
  out costs nothing more.
- **Context menus are drawn by the page in every client** (`ContextMenu.vue`). They need no shell work.
- **Copying today:**
  - `TextEditor.vue` and `SheetGrid.vue` handle `@copy`.
  - `object-clipboard.ts` listens for `copy` on the document in the capture phase.
  - Nothing looks at the role.
- **E7.12 (the ai action catalog, branch `e7-12-ai-action-catalog`)** plans three "Methods" columns in the same
  workbook. An `.xlsx` cannot be merged by git: see §8.

## 3. Where each piece goes, and why

### 3.1 The one definition (diagram, column 1)

**The definition moves to `clients/contract/` (D1643)**, beside the shell contract, as a small package of its own:
`clients/contract/pyproject.toml` (project `claudia-menus`) and `src/claudia_menus/`. It is pure data with no
dependencies, and it runs on Python 3.12 like the Linux client. Its tests stay in the Linux client
(`clients/linux/tests/test_manifest.py`), because they also check it against that client's contract module and app
identities; one of them checks that the package imports with nothing but its own folder on the path.
- **Moves:** the dataclasses, the per-app manifests, `for_start` and `on_start`, and `describe()`.
- **Stays in the Linux client:** `menu_xml` and `menu_elements`, which turn the definition into GTK's menu XML.
- **Changes:** `UnknownApp`, which the manifest takes from the client's `identity.py`, becomes the package's own
  `KeyError`.

The move is the first commit of the build, with no change of behaviour. Everything that reaches the old place follows:
- the Linux client's `window.py`, `bridge.py` and its tests;
- `clients/linux/pyproject.toml`, as a path dependency;
- `start-linux-client.sh` (`PYTHONPATH`);
- `packaging/debian/build-deb.sh`, which copies the package beside the client;
- `clients/neutralino/tools/generate_menu.py` and its `pyproject.toml`;
- `scripts/generate_keys.py`, `scripts/menu_audit.py` and `scripts/extract_i18n.py`;
- the ruff and vulture paths in the root `pyproject.toml`;
- the paths of `.github/workflows/deb.yml`.

Then the definition grows by three things:
- **`Action.fits`:** the workbook's "Fits when" words, verbatim. An example is `"role: editor or owner · selection:
  something"`. Being verbatim is what makes the test of D1605 a plain string comparison (D1646).
- **`Action.keys: Keys(default, macos)`** in place of `accelerators`. macOS has its own key where it collides with
  macOS itself (D1616). The web on a Mac uses it too (D1648).
- **`Manifest.context_menus`:** one `ContextMenu` per context (object, cell, paragraph, table, pivot table, slide…), in
  the workbook's order. They are in the definition because the Shortcuts dialog (D1604) lists them, and the workbook
  test checks them.

`scripts/generate_keys.py` becomes `generate_menus.py`. It writes `web/app/lib/menus.generated.ts`, which holds the
whole definition (`keys.generated.ts` merges into it), and the Neutralino JSON as today. A test fails when either is
stale, as one does for the keys today.

### 3.2 Judging (diagram, column 2, top half; `web/app/lib/fits/`, new)

- **`Condition`:** one per phrase of the workbook ("role: owner", "selection: a pivot table"). It has:
  - its `reason`;
  - `holds(facts)`;
  - `why(t)`, the notice ("Only an owner can do this."); an entry of the definition may carry a sentence of its own
    instead (D1650);
  - `plain(t)`, for the Shortcuts dialog ("owners").
- **`CONDITIONS`:** the registry, words → condition. Adding a condition is one entry here, as D1601 asks.
- **`Rule.parse(words)`:** splits at "·" and looks each phrase up. An unknown phrase throws, and a test parses every
  rule in the definition, so a typo in the workbook or the manifest fails the build rather than hiding an entry.
- **`Reason`:** the six reasons in the order of D1642, each with its tag for the Shortcuts dialog.
- **`Facts`:** what the conditions read.
  - The shared part (role, desktop or web, a real ai, the server's tools) comes from `DocumentFrame` and the
    session.
  - The app part (undo, pivot tables, objects; what is selected) comes from each workspace.
  - Several selected things fit only when all fit (D1601); `selection.kinds` carries them.
- **`FitPolicy`:** the trial (D1606), one setting per reason plus overrides per action, read from the page's URL.
  The desktop shells add the parameter from their settings file when they load the page. That keeps one place that
  reads it.
- **`judge(rule, facts, policy, id) → Verdict { shown, enabled, why? }`:** a pure function, tested with plain data.
  The first failing condition in reason order names `why`.

### 3.3 Using the verdict (diagram, column 2, bottom half)

- **`ActionHandlers`:** what each workspace keeps of its menus. It is a map from id to
  `{ run(target?), label?(), checked?() }`; `label()` covers "Undo Add Container". The 55 `disabled:` expressions
  become conditions, or go where they were only a role check spelled out by hand. A test checks that every action of
  the app's definition has a handler and no handler lacks an action. It replaces the id drift guard
  (`menu-dispatch.ts`).
- **`MenuAssembler`:** definition × handlers × verdicts gives `Menu[]` for `MenuBar.vue` and `MenuItem[]` for
  `ContextMenu.vue`. Those two components keep their shape: greyed is `disabled` as today. The assembler:
  - leaves hidden entries out;
  - collapses separators and empty submenus;
  - turns an empty menu into its one "why" line (D1603);
  - hands the states to the shell.
- **`menuShortcuts`** takes its keys from the definition instead of the drawn menus, so a hidden entry keeps its key.
  A key whose verdict is "does not fit" shows `notice(why)` (D1604), through the existing notice and its `role=status`
  region (`notice-said.ts`).
- **`ShortcutsDialog.vue`** lists the whole definition, menus and context menus. It has the switch What Fits Now /
  Everything, the tags of D1642, and the rule in plain words, from `Condition.plain`.
- **`CopyGuard`** (D1640) catches `copy`, `cut` and `dragstart` in the capture phase on the document and on History &
  chat. It judges `edit.copy` with the same rule as the menu entry, so the guard and the menu cannot disagree. A
  refused copy shows the notice and copies nothing.
- **Paste As ▸ Plain text** (D1641) checks for text when it runs, in its handler.

### 3.4 The shells (diagram, column 3)

- **Contract, v1, additive:**
  - `action_state.states[id].visible` (optional);
  - `action_state.empty`, menu id → the "why" text (optional).
  - An older shell ignores both and greys instead, which is a safe fallback.
- **GTK:** `for_start` becomes the general `visible_only(manifest, keep)`.
  - The front page is that filter with `keep = on_start`, so one mechanism hides in both places.
  - A changed model is put on its menu button when that menu is closed. An open menu stays as it opened (D1603).
  - The "why" line is an item whose action is never enabled.
- **Neutralino:** `applyActionStates` leaves out hidden items, collapses separators and adds the "why" line.
- **The collapse rule** (separators at the start, end or doubled; empty submenus) exists twice, in TypeScript (page and
  Neutralino) and in Python (GTK). One table of cases in `clients/contract/fixtures/` is run by both test suites, so
  the two cannot drift.

### 3.5 What holds it to the workbook (diagram, column 4)

`tests/test_menu_workbook.py` (D1605) reads `claudia-menus.xlsx` with openpyxl and compares it with the definition,
app by app:
- entries and their places;
- keys per platform;
- "Fits when" verbatim;
- context menus.

`scripts/menu_audit.py` keeps the live capture of what the apps show. It serves diagnosis and is not a gate.

## 4. The seams to test (to agree under /tdd)

- **Pure TypeScript, Vitest:**
  - `Rule.parse` and `judge`;
  - the assembler (hide, grey, collapse, the "why" line);
  - `menuShortcuts` with a hidden entry;
  - the copy guard's decision.
- **Pure Python, pytest:**
  - the definition against the workbook;
  - `visible_only`;
  - the collapse fixture.
- **The contract:** schema tests for `visible` and `empty`.
- **E2E (Gherkin, next step):** a viewer's Insert says why; Ctrl+C as a viewer gives the notice and leaves the clipboard
  as it was; a hidden entry's key gives its notice; the trial setting switches a reason to grey.

## 5. Order of work (vertical slices, each red then green)

1. ~~**The definition moves** to `clients/contract/` with everything that reaches it (D1643); nothing else changes.~~ Done.
2. ~~**The definition grows** (`fits`, `keys`, context menus), rebuilt to the workbook (E5.23's content), with
   the workbook test.~~ Done; `generate_keys.py` keeps its name until slice 4 writes the whole definition for the web.
3. ~~**Judging:** `fits/`, pure, with every rule of the definition parsing.~~ Done.
4. **The web from the definition**, one workspace at a time, everything at "grey" first, so behaviour only changes
   where the workbook moved entries. Then the trial's default, hide.
5. **Keys and the Shortcuts dialog** (D1604, D1642).
6. **The shells:** contract fields, Neutralino, GTK.
7. **The copy guard and Paste As ▸ Plain text** (D1640, D1641).
8. **I18N:** every new text (the notices, the "why" lines, the tags, `plain`) in `po/`; the German menus with
   "Formatvorlage" (D1618).

## 6. Decided (2026-11-25)

| | Decided | Decision |
|---|---|---|
| A1 | The definition moves to `clients/contract/` as a package of its own (the owner's choice over leaving it in the Linux client). | D1643 |
| A2 | The web's menus are assembled from the definition plus a map of handlers per workspace. | D1644 |
| A3 | Only the page judges; the shells draw `visible` and `empty` from `action_state` (contract v1, additive). | D1645 |
| A4 | Rules are kept as the workbook's words and parsed against a registry of conditions. | D1646 |
| A5 | The trial setting travels as a URL parameter; the desktop shells add it from their settings file. | D1647 |
| A6 | The web on a Mac uses the macOS keys too. | D1648 |
| A7 | One branch at a time edits `claudia-menus.xlsx`: `menus` now, E7.12 after `menus` is merged. | D1649 |

## 7. What is not decided here

- The Gherkin scenarios: `specs/menus/menus-that-fit.feature`, approved 2026-11-25.
- Whether people get the hide/grey choice after the trial (D1606).

## 8. Not verified, and risks

- **GTK:** replacing a menu button's model only while the menu is closed is from the GTK documentation, not tried here.
  A headless GTK test can check it.
- **WebKitGTK:** I assume Edit ▸ Copy, which runs as an editing command (`Kind.EDITING`), fires the page's `copy`
  event, so the copy guard sees it. Not tried. If it doesn't, the GTK shell must send Copy as a page action for a
  viewer.
- **Size:** slice 4 touches the three workspaces (about 2,900 lines). The risk is behaviour that only the workspace
  knew about, such as an entry greyed for a reason nobody wrote down. Every `disabled:` expression is listed before it
  is replaced, and one that matches no workbook condition is brought to the owner.
- **The move** (D1643) touches the Debian package and the CI paths. The Debian build and the Neutralino generator
  are run after it, before anything else changes.
- **The workbook as a binary file** (D1649): two branches that both change it cannot be merged. One has to be redone by
  hand.
- **The copy guard is a barrier, not protection** (D1640).
