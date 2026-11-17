# E3.13 f: Server settings ▸ Fonts, first version (2026-11-16)

Built from boards 1 and 2 (`notes/mockups/fonts-1-server-settings.svg`, `fonts-2-add-fonts.svg`), with the owner's
answers of 2026-11-16: the three answers for who may receive fonts now (D1041), and the core page first; fetching
from a pinned list, Edit stand-ins… and Remove file… come in a second patch. Architecture:
`notes/mockups/e3-13-architecture-server-fonts.svg`. Screens as built: `notes/mockups/fonts-built-1-page.png`,
`fonts-built-2-check.png`, `fonts-built-3-not-usable.png`.

## What is where

- **`claudia_fonts.adding`** (new): `check_files` says what each font of an upload would become (`added`, `added`
  with `replaces`, or `left-out` with a code), a `.zip` opened into its fonts; `add_collection` writes the usable
  files and the record into a new folder (written in a hidden folder and renamed, so a collection appears whole);
  `rename_collection`, `remove_collection` (only directly under the root of added collections).
- **`claudia_fonts`**: `CollectionRecord.may_go` (`anywhere` / `this-server`, D1041), `added_by`, `added`; `Problem`
  and `FontProblem` carry a `code` (and `detail`, `family`, `style`) so the page says why in the App Language;
  `Catalogue.collections` and `stands_in_for`.
- **`claudia_server.fonts`**: `FontService` knows where each collection comes from (shipped, operator, added),
  reads them again with `reload()`, and hands This-server fonts only to the server's people (`local`).
- **`claudia_server.admin_fonts`** (new): `/api/admin/fonts` and its `files`, `check`, `collections` routes.
- **Web**: `AdminFonts.vue` (the page, fourth in `AdminShell.vue`), `AddFontsDialog.vue`, `MayGoBadge.vue`;
  `lib/admin-fonts.ts` (what the page shows, as plain functions) and the font calls of `lib/admin-api.ts`.

## Differences from the boards

- Board 1 shows a family "3 of 4" with Remove file…: a file the check leaves out is never written, so a family added
  on the page has no such line. The line appears for files an operator put on the disk (shown in the screenshot with
  an operator collection); Remove file… is not built.
- The starter set is nine collections on disk; the page shows them as one card, "Shipped with Claudia", as drawn.
- "Edit stand-ins…" and the pinned-list fetch are not on the page yet (owner's choice). The sentence under the table
  names the same-width families from the catalogue rather than a fixed list.
- The page's actions are buttons on the page, not menu entries, so there are no new shortcuts; the dialogs close with
  Esc (D128).

## Places this reaches

| Place | State |
|---|---|
| `GET /api/admin/fonts`, `files`, `check`, `collections` | done + test (`test_server_admin_fonts.py`) |
| `GET /api/fonts` and the font files: This-server fonts to the server's people only | done + test (`test_server_fonts.py`) |
| adding, renaming, removing on disk | done + test (`test_fonts_adding.py`, `test_fonts_catalogue.py`) |
| the page and the dialog (web) | done + test (`tests/admin-fonts.test.ts`; `e2e/admin-fonts.cjs` adds, renames and removes on a real server, with `scripts/make_admin_fonts_sample.py`) |
| i18n | done: every string through `t()`, German translated, pseudo-locale made |
| the web client's layout and print fonts | gap → E3.13 backlog: the client does not send the access secret when it loads `/api/fonts`, so This-server fonts reach a document's people only on a server without a secret |
| PDF export and office exports | gap → E3.13 backlog: nothing checks This-server fonts yet (the print preview embeds what it lays out) |
| LaTeX typesetting | done + test (CODE-50): the plugin asks for the current catalogue on every job (`test_render_latex_fonts.py`, `test_server_fonts_latex.py` with the real XeLaTeX) |
| desktop clients | not affected: they show the same web bundle, and none has a menu entry of its own for the server settings |
| document import and export | not affected: a server setting, not part of a document |

## For whoever continues

- `e2e/admin-fonts.cjs` takes `CHROMIUM` for a browser of one's own when Playwright's is not installed.
- After naming the first administrator, the settings page stayed on the setup form until reloaded: CODE-48, fixed
  2026-11-17; the e2e script goes on without a reload.
- Files chosen in Add fonts… are held on the server per administrator until added, let go of (the dialog does so on
  Cancel, Start again, closing and a failed upload) or 30 minutes pass; the limits come with the page (`limits`), so
  the dialog says them before sending (CODE-49).
- LaTeX needs a font of the family "Latin Modern Roman" (at least `lmroman10-regular.otf`) and `latinmodern-math.otf`;
  it asks the font service for the catalogue on every job, so added fonts are used at once (CODE-50, claudia-render
  0.2.0). The service-level cache of finished pictures (`RenderService.render`) does not have the fonts in its key, so
  a picture made before a font of the same family and style was replaced stays (reported to the owner, not fixed).
- Containers (CODE-51, CODE-52): a document that is opened draws its containers that have text and no picture, the last
  outcome of each is sent with `renderings` (`outcome`), and a TeX message comes back whole (`max_print_line`, and
  `parse_log` joins the lines a message goes on in). The program set as `xelatex` must be a LaTeX engine: with plain
  `xetex` or `pdflatex` the message is now "…fontspec package requires either XeTeX or LuaTeX" or "Undefined control
  sequence". Open: the failure text is clipped in a small frame (CODE-53), pictures are kept without the fonts in their
  key (CODE-54).
