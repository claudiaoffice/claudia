# E1 core: names and descriptions, the way back, the what-if desk, the font report (D1300–D1320)

Branch `e1-core`. Built to `notes/e1-architecture.md` with the owner's answers A1–A8. Decisions: D1304, D1306–D1313, D1317–D1320.

## What was built, by package

| Where | What |
|---|---|
| `claudia-core` | `WhatIf`/`Proposal` (`what_if.py`): a proposal is plain data (base, commands, author); its footprint is worked out when it is applied from `materialize(base)`; it is *outdated* if a later step overlaps or moves a place of the footprint; no rebase; applied as one `Batch` with `via`. `ProposalOutdated`. `Entry.via`. `StyleBook.font_families`. |
| `claudia-composes/-computes/-creates` | `block_descriptions` / `DescribeThing`, generic names at creation, headings named by title; `requirements()` (fonts the model needs). |
| `claudia-composes-io` | docx/odt: names a person gave are bookmarks (docx names are sanitised: letters, digits, `_`; `_`↔space coming back); generic and technical bookmarks are ignored; descriptions as review comments (docx `comments.xml`, odt `office:annotation`) only on request; comments are never read back. |
| `claudia-server` | `thing_details`, `name_and_describe`, `name_and_describe_range`, `what_if_*` and `as_what_if`, `font_report`, `export_choices`, `export_office(description_comments)`; `import_state(fmt, data, locale)` names unnamed things on import. |
| web | `NameAndDescribeDialog` (replaces `ObjectDescriptionDialog`), `lib/name-and-describe.ts`, `lib/use-name-and-describe.ts`; the way back in `base-session.ts` (`WayBack`, `ScrollBack`, `setAnchorProvider`, `goBack`, `clearBack`), `BackChip.vue` over the view (out of `SidePanel.vue`), `FontReportBanner.vue`, the export tick, *View ▸ Back where I was*, *Format ▸ Name & describe…* in composes too. |
| clients | `view.back` and the composes entry in the manifest; the Neutralino menus regenerated; View is drawn by the page, so there is no native code. |

## The way back

See D1319. `goToThing` takes `{container, anchor}` before every jump; each view reports its anchor (`lib/view-anchor.ts`
for the cell anchor of computes). `goBack()` shows the container and sets `state.scrollBack` (a new object with a rising
`nonce` each time), which the view watches and scrolls to. `clearBack()` is called from typing and clicking in each view.

## Things to know

* **Bug found and fixed on the way:** the highlight of a pointed thing was never cleared by its timer, because the
  timer compared the raw object with the reactive proxy read back from state. It is compared as read back now.
* The patched-original export path (a file an import kept) does not write comments: with the option on, a new file is
  written and the answer's `losses` say `not-patched`. It does not update bookmarks for renamed paragraphs either.
* Descriptions of tables and lists are stored, but only paragraphs and headings become comments on export (they are
  keyed by block id).
* docx bookmark names are lossy (`_` and space are the same on the way back).
* The footprint of a multi-command proposal is read in each command's own coordinates: conservative, can call a
  proposal outdated that is not.
* The what-if desk is not used by the AI yet (E7.8); `Account.assistant()`'s allowed methods do not list `what_if_*`.
* `thing_described` is not handled by the web (the dialog asks the server when it opens, so nothing shows a stale
  description).
* Get on the font banner goes to Server settings ▸ Fonts (D1320).

## Not run

* The E2E suite (`tests/e2e`, the scenarios of `specs/objects/names.feature` and `specs/container/requirements.feature`):
  Playwright's Chromium is not installed here. Their `@pending:e1.*` tags are therefore **left on**; nobody has seen them pass.
* No real browser, so the key Ctrl+Shift+B was not tried in Chrome, Firefox, Safari, WebKitGTK or WebView2 (D1319).
* The GTK and Neutralino shells were not started; their manifest and menu tests ran, the Neutralino shell tests pass.

## Documentation

API snapshots (`tests/api/*.json`) and the changelogs of core, composes, creates, computes, composes-io and server are
updated; the web has no Sphinx part (its types are in the TypeScript sources).
