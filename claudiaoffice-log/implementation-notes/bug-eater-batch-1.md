# Implementation note: bug eater, batch 1 ("small and certain")

Written 2026-11-24, branch `batch-1` (from `main` at `54fee1d` with `backlog` merged). The brief is `notes/bug-eater.md`,
the queue `notes/bug-eater-queue.md`; decisions D2001 and D2002 (the bug eater's block is D2001–D2100). One commit per
item, its message starting with the item's ID. The seams of the tests are the "First test" column of the queue, which
the owner approved with the batch.

## What changed, per item

| Item | Change | Test written first (seen red) | Escaped because |
|---|---|---|---|
| PROC-15 | `tests/test_bugtracker.py`: each index heading counts its rows, no row under *Open* says fixed, no item in both tables, *Open* is in priority order. CODE-17, CODE-75, CODE-76 (already fixed) moved to *Fixed*; the stale points of the triage's section 7 corrected | that test | missing test |
| SEC-06 | The server's own certificate is an end certificate (`ca=False`, no certificate signing); one of ours made before is replaced at the next start (D2001) | `test_server_certs.py`: a certificate for another name signed with the server's key is refused; a client that trusts exactly the server's certificate connects; an old authority certificate is replaced | missing test |
| SEC-14 | `/api/swagger` only with `--api-docs` (`create_app(api_docs=...)`); the landing page links it only then. `/api/openapi.json` stays (no third party) | `test_server_api_docs.py` | spec gap |
| SEC-16 | `PUT /api/admin/settings/typeset` runs the program once in the typesetter's sandbox and keeps it only when it names itself (`claudia_server/typeset_check.py`, D2002) | `test_server_admin_api.py`: a program that is not xelatex / pdftocairo is refused; one that names itself is kept | missing test |
| CODE-20 | The Dockerfile copies `ghcr.io/astral-sh/uv:0.11.32` | `tests/test_dockerfile.py`: every pulled image names a version that is not `latest` | missing test |
| CODE-54 | `Plugin.cache_token()` is part of `RenderService`'s key; `LatexPlugin` gives the font catalogue's digest | `test_render_service.py`, `test_render_latex_fonts.py` | missing test |
| CODE-56 | `WorkbookModel.sheet_ids_used` (only grows, in the snapshot); `_fresh_sheet_id` skips those ids | `test_server_computes.py`: a new sheet never gets the id of a removed one (by undo and by `RemoveSheet`; before the fix the undo failed with `UndoConflict`) | missing test |
| UX-75 | `AiRuntime.apply` publishes `ai_consent_changed` (`{provider}`, no sender) to every open document (`Hub.tell_open_documents`) | `test_server_ai_provider_settings.py` | missing test |
| PROC-31 | `render_pot` writes each text's files, not lines; the three catalogues regenerated | `test_extract_i18n.py`: moving a text to another line leaves the template as it was | missing test |
| CODE-36 | `safeStorage`, `safeSessionStorage`, `remembered`, `rememberedText`, `remember` only in `web/app/lib/storage.ts` (11 users); it guards every storage call, the page's memory holds only what the browser refused; the callers' own guards are gone | `web/tests/storage.test.ts` (a refusing browser: `web/tests/refusing-browser.ts`) | missing test |
| CODE-71 | Every key hint of the object menu comes from the manifest; "Del" and "Enter" are translated ("Entf", "Eingabe") in every menu | `web/tests/object-menu-hints.test.ts`, `shortcuts.test.ts` | missing test |
| UX-63 | The print preview names the exit record, not the history (German: "Export-Log", the owner's word) | `web/tests/print-preview-wording.test.ts` | spec gap |
| UX-66 | `--apricot-dark` and `--shadow-raised` tokens; the Styles dialog has no colour literal left; no component may have more literals than the shrinking allow-list grants (40 files today) | `web/tests/tokens.test.ts` | missing test |
| UX-67 | Heading and Numbering stay native selects inside the app's field look | `web/tests/style-spec-selects.test.ts` | missing test |
| UX-74 | An owner can withdraw a consent given earlier while the server has no Claude, and is told that the server has no Claude | `web/tests/ai-provider.test.ts` | spec gap |
| UX-32 | The document page has one `header` (menus, banners, toolbar), `main`, the panel's `aside` and the `footer` | `web/e2e/grid-a11y.cjs`: axe `landmark-one-main` and `region` in the three apps | missing test |

**Versions:** claudia-server 0.45.0 (`create_app(api_docs)`, `Hub.tell_open_documents`), claudia-render 0.3.0
(`Plugin.cache_token`), claudia-computes 0.12.0 (`WorkbookModel.sheet_ids_used`); changelogs and API snapshots. The
changes that were under *[Unreleased]* in these three changelogs (E6.31, CODE-55) were folded into the new versions,
which ship them.
**Web coverage thresholds** raised to what the tests now reach: 90 / 87 / 86 / 91 (statements, branches, functions, lines).

## Assumptions (the owner may veto)

- SEC-06: replacing a certificate of ours that is an authority changes its fingerprint once; a pinned client asks again.
- SEC-16: a program that is not installed yet can no longer be saved ahead of installing it (D2002); the banner of an
  accepted program is not shown on the settings page yet.
- SEC-14: the switch covers the interactive page only; `/api/openapi.json` stays public.
- CODE-20: the tag `0.11.32` is the uv used here; that the image exists on ghcr.io could not be checked from here.
- UX-75: the event reuses `ai_consent_changed` (the tracker's fix) with other data; the web client only re-reads on it.
- UX-63: the owner chose "Export-Log" as the German for "exit record" (2026-11-24).
- UX-66: the pill keeps its light look in dark mode, so `--apricot-dark` has no dark value.

## Found along the way (not fixed; the owner decides)

- **Size 3:** `.hiddenflag` in `StylesDialog.vue` sets `color: var(--text)` on a light mist background, so in dark mode
  the text turns light on light (BITV 1.4.3).
- **Size 2:** the administrator API answers in English only: its refusals (`HTTPException` details, SEC-16's sentence
  among them) are not `msg(...)` and are shown as they are on the settings pages.
- Context-menu entries with no entry in the manifest, so no key: "Snap to grid" / "Release from grid", "Move to Slide",
  "Gap…" and the four wrap modes (the project rule: every menu entry has a shortcut; see `claudia-menus.xlsx`).

## Review (`code-review` at the end of the batch)

Both axes ran over the batch. Fixed after the review: the changelogs (above), claudia-computes' version, a flag
argument in `_web_routes`, an unused return value of the typesetting check, a certificate test that patched the module's
internals, two comments that said what instead of why, the storage leftovers of CODE-36, the owner's missing note in
UX-74 (its first commit had hidden it from an owner, which `ai-consent.feature` would have shown), the Styles dialog's
last colour literal, a test of CODE-56's own scenario, the stale tracker points of PROC-15, the compiled `.mo`
catalogues, and the commit messages of the follow-ups are in the imperative (coding-standards §10; the first
commits of the batch are not).

**Left as they are, and why:**
- SEC-06: the Linux shell's pinning is not run against the new certificate in a test. It reads the certificate with
  verification off and compares the fingerprint (`trust.py`, `may_override`), so whether the certificate is an
  authority does not reach it.
- SEC-16: the refusal is English, as every answer of the administrator API is (reported below as a bug).
- CODE-20: the tag is pinned, not the digest: the registry cannot be reached from here to read it.
- UX-66: the rule allows the literals other components have today (the tracker asked for none outside `tokens.css`);
  they may only go down. `StyleBar.vue` and `StyleMenu.vue` have the literal `--shadow-raised` now names.
- UX-67: the field look is checked; focus ring, contrast and target size were measured by hand in the running app
  (2px outline, 37px tall), not by a test.
- Scope beyond the items: CODE-71 translates "Del" and "Enter" in every menu (they were English in German);
  CODE-36 raised the web coverage thresholds to what the tests reach.

## What was run

- Python: the whole suite (`pytest`, without `tests/e2e`), the gate `check_debt.py --fast`, ruff, mypy, the docs build
  (`sphinx-build -W`; it caught a docstring of CODE-56, fixed).
- Web: `npm run lint`, `npm run typecheck`, `vitest` (2,019 tests), `npm run coverage` (90.2 / 87.1 / 86.2 / 91.6).
- Layout: its typecheck and 265 tests (after `npm ci` in `layout/`).
- E2E: `./run-e2e.sh core` in Chromium (the installed one, `CLAUDIA_CHROMIUM=/usr/bin/google-chrome`); the extended
  `grid-a11y.cjs` and ten more regression scripts by the web helper.

## What could not be run

- **Firefox**: Playwright's browser download is blocked here (`cdn.playwright.dev`), so no E2E ran in Firefox.
- **The desktop clients' windows** (GTK, Neutralino on Windows and macOS): only their unit tests ran (`linux client
  tests` in the gate). No hand check on the GTK client (PROC-30's rule, agreed today, asks for one per batch that
  touches the UI).
- **The Docker image** was not built (CODE-20's tag is unverified).
- **Import and export**: no item of this batch changes them; their tests ran with the suite.
- `print.cjs` needs the server's fonts, which need the internet; not run.
