# One document frame, and every package under the versioning policy

Branch `main`, 2026-11-10. The first two suggestions of the QA round (`implementation-notes-qa-2026-11-10.md`,
"Suggestions, not done"), done at the owner's request. No decision changed; this note records how.

## 1. Three workspaces, one frame

Before: only creates (`SlideWorkspace.vue`) used `DocumentFrame.vue`. Computes (`Workspace.vue`) and composes
(`TextWorkspace.vue`) each built the same window by hand — menu bar, side panel, the frame dialogs
(checkpoint, share, shortcuts, about, owner hand-over, leave, export, delete), the shell bridge, the shared
shortcuts — and spelled out the same eighteen menu entries.

After:

* **`web/app/lib/document-menus.ts`** builds the menu items every app has, once: `fileMenu` (File with its Manage
  submenu, D120/D141), `undoRedoItems`, `clipboardItems`, `panelItem`, `darkItem`, `authorsItemUnavailable`,
  `askItem`, `configMenu` (Shortcuts, and App Language from `LANGUAGES`) and `helpMenu`. Plain functions over a small
  `DocumentMenuContext` (`t`, the role, `open(dialog)`, `leave()`, `save()`), so `web/tests/document-menus.test.ts`
  checks them without mounting anything. The shortcut hints come from `sharedShortcuts` (`SHARED_HINTS`), so a
  menu cannot show a chord the window does not listen for. Each app assembles its menus from these blocks plus its
  own items, in the same order as before.
* **`DocumentFrame.vue`** takes `app` (`computes`/`composes`/`creates`: the shell bridge's and About's app),
  `extraShortcuts` (composes' Shift+F10 for the style menu) and `shortcutNotes` (each app's lines in the Shortcuts
  dialog), and has a `side-top` slot (composes' suggestion list above the panel). It owns the frame dialogs
  (`FrameDialog`), opened through `openDialog`; an app keeps only its own (computes: sheet name, image, chart, row
  and column size, styles, colours; composes: styles, colours).
* **`BaseSession.flush()`** (does nothing) and `TextSession.flush()` (sends the words still being collected): the
  frame calls it before a checkpoint and before an export, which composes used to do in its own copy of those
  dialogs. Moving them into the frame without this would have exported a text without its last few words.

Sizes: `Workspace.vue` 835 → 623 lines, `TextWorkspace.vue` 517 → 308, `SlideWorkspace.vue` 381 → 328;
`DocumentFrame.vue` 212 → 227 and `document-menus.ts` 192 new. 477 lines added, 924 removed in `web/`.

Checked: `npm run typecheck`, vitest (524 tests, 10 new), the Python e2e (`tests/e2e`) and all seven Playwright
scripts in `web/e2e/`, and screenshots of each app's window and its menus taken on `main` and on this change —
pixel-identical except the history's timestamps. `po/claudia.pot` regenerated: the same 153 messages, only their
source lines moved. The extractor (`scripts/extract_i18n.py`) only finds a bare `t('…')`, which is why every builder
starts with `const { t } = c` instead of calling `c.t('…')`.

## 2. Every package under the versioning policy

`claudia-computes`, `claudia-composes`, `claudia-ai`, `claudia-opc-io`, `claudia-computes-io`,
`claudia-composes-io`, `claudia-creates-io` and `claudia-test-documents` now follow `docs/versioning.md` like the
others: `_version.py` with `__version__ = "0.1.0"`, `"__version__"` in `__all__`, the version read by hatchling
(`dynamic = ["version"]`, `[tool.hatch.version]`; `uv.lock` updated), a `CHANGELOG.md` whose 0.1.0 entry records the
surface as it stands, a page in the documentation (`docs/changelog-*.md`), and an API snapshot
(`tests/api/<package>.json`) that `tests/test_public_api.py` holds them to. `claudia_test_documents` is in the API
reference now as well (`docs/api/apps.rst`).

What the stricter tests found, and what was fixed:

* `claudia_computes` had 27 public methods and two classes (`Sheet`, `WorkbookModel`) without a docstring — in
  `refs.py`, `region.py`, `events.py` and `model.py`. Written.
* `claudia_computes.__all__` named `column_name`, `content_of`, `parse_input` and `parse_range_ref` twice.
* `claudia_test_documents.ADAPTERS` holds functions, whose repr carries a memory address, so its snapshot changed on
  every run. `scripts/api_surface.py` now strips addresses from values the same way it already did from
  signatures (`portable`, with a test).
* Three of `claudia_test_documents`' docstrings broke the docs build once the module was documented (an indented
  line, two references to names that are not public). Fixed.

## Still open from that list

Dependencies (`npm audit`, SEC-08), `.gitlab-ci.yml`, coverage and a web linter (CODE-01), the `state.py` docstring
(CODE-05).
