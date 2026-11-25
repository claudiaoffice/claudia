# Implementation notes

Moved from the project context on 2026-11-05. One file per epic or theme; the project context is no longer the place
for these. Companion files one level up: `Projects/claudia-office/_tasks/` (stories, E-numbers), `decision-log/` (D-numbers, including the
renumbering table), `bugtracker.md` (SEC/PERF/UX/CODE/PROC/DOC items) and `qa-recommendations.md`.

| File | Covers | Written |
|---|---|---|
| `product-vision.md` | The reasoning behind D58–D72: stories across the suite, process help, composes and creates character, who it is for | 2026-11-02 |
| `design-system.md` | Colour, typography, logos, layout and illustrations; the reference for the web client and the shells | 2026-11-02 |
| `demo-analysis.md` | The original `gtk_sheet` demo read statically: what to keep, the proposed split, and the gaps against the decisions | 2026-11-01 |
| `e0-shells-and-web-surface.md` | E0.1, E0.2, E0.3: the Linux and Windows spike results, the web-surface options and why system web views won | 2026-11-01/02 |
| `e0-3-neutralino-windows-macos.md` | Neutralino 6.8.0 run on a Mac and on Windows 11: results, the `NE_CL_IVCTOKN` token bug and its fix, menu roles, printing, About, what is untested, and the open question of how the real frontend reaches the shell (D156–D159). Evidence in `spikes/e0-3-neutralino/results/` | 2026-11-07 |
| `e1-kernel.md` | E1.1–E1.9 as built, the design points behind D45–D49, and the project-hygiene rules | 2026-11-02 |
| `e2-container-and-encryption.md` | E2: threat model, format, key slots, journal, and the three delivered slices with their findings | 2026-11-02/03 |
| `e3-server-and-security.md` | E3.1 as built, and the SEC-01/02/07 fixes with their breaking changes | 2026-11-02/03 |
| `e3-fonts-and-typesetting.md` | E3.3, E3.4, E3.10: the two libraries, the probe results, Windows, and the user's own LaTeX | 2026-11-03 |
| `e3-3-font-management-ui.md` | Proposal, not built or decided: the server's catalogue in Server settings ▸ Fonts, the document's own fonts at Format ▸ Fonts… (pinned by hash, optionally kept inside the document), adding a missing font to the document rather than the server; open questions; stand-ins made visible on import, while working and on export; mock-ups `mockups/fonts-1…7-*.svg`; architecture of slices a and b `mockups/e3-13-architecture-slices-a-b.svg` | 2026-11-16 |
| `e4-e6-formulas.md` | The formula engine as built, the proposed decisions, and what was measured | 2026-11-03 |
| `e5-linux-client.md` | The GTK shell, the shell contract, the menu mapping, and the compatibility notes | 2026-11-03 |
| `e7-ai.md` | The `ai` user design and the E7.1 port: packages, decisions taken while porting, what is unverified | 2026-11-01/02 |
| `e7-ai-agent-design.md` | Proposal: the AI sees the document and the effect of its actions (read tools, effect report, loop), the local model in all three apps (composes fails, creates has none), Claude as a provider in the server settings; decided D261–D266 (rights of the asker, act/suggest per person with suggest as default, proposals as scratch previews, two opt-ins for a remote AI, an acting AI for creates, Claude by API key); mock-ups `ai-settings-provider.svg`, `ai-panel-observe-act.svg`, `ai-suggest-mode.svg` | 2026-11-11 |
| `e9-composes.md` | The composes model, the web demo history, and the styling work | 2026-11-02/03 |
| `e9-print-and-layout.md` | E9.4/E9.6/E9.14/E3.3 on branch `layouting`: the `@claudia/layout` library part by part and what the other apps reuse, the print preview, fonts for clients, choices made while building, measurements, and what was left for E9.23, E9.24, E6.19, E10.18 (D901–D911); mock-up `mockups/print-preview.svg` | 2026-11-12 |
| `e9-hyphenation-and-svg.md` | E9.25/E9.26 on branch `layouting`: the Knuth–Plass breaker and hyphenation (elements, passes, demerits, soft hyphens), the patterns, the SVG reader and how it reaches the PDF and the preview, the comparison with librsvg (D912–D916); screenshots `mockups/print-preview-language.png`, `mockups/style-hyphenate.png` instead of agreed mock-ups | 2026-11-12 |
| `e10-print-slides.md` | E10.18 on branch `layouting`: printing slides and handouts, page setup and language moved to the kernel, one print preview for composes and creates, the consistency choices (D917, D918); screenshots `mockups/print-preview-creates-*.png` instead of agreed mock-ups | 2026-11-13 |
| `e10-2-presenter-mode.md` | E10.2: presenter mode design; answers of 2026-11-13 (Markdown notes, frozen show, rights, keys), planned time per slide and in total, what is still open; mock-up `mockups/presenter-mode.svg`; spike in `spikes/e10-2-presenter-window/` | 2026-11-13 |
| `e9-composes-lists.md` | Agreed and built (kernel, server, web; creates bullets open): ordered and unordered lists as a (list, level) mark on a paragraph with named schemes, numbers derived in the kernel, and the seam for numbered headings and referencable anchors (E9.21, E9.22); mock-up `composes-lists.svg` | 2026-11-13 |
| `e9-composes-outline-references-toc.md` | Proposal (nothing built): outline levels on styles, numbered headings from a style that points at a list, numbering schemes as document data and the All numbering dialog, references as inline fields at a U+FFFC, the table of contents as a generated paragraph, page numbers in at most three layout passes, files, slices S0–S6 (E9.22, E9.30, E9.31); also why `lists-and-anchors-in-compose` is moved to main rather than merged; mock-ups `composes-numbered-headings.svg`, `composes-references.svg`, `composes-table-of-contents.svg`, class diagram replaced by `text-structure-architecture.svg` (see the next row) | 2026-11-16 |
| `text-structure-across-apps.md` | Plan, steps A and B built on 2026-11-16 (heading levels on styles; list markers in print; one component for a text box's words; guard tests): the entities for outline levels, numbering, lists, references and contents in all three apps; the `ParagraphHost` seam each app implements (reading order, where a paragraph is), the shared `TextStructure`, what moves from composes into `claudia-core` and a shared server module, what is replaced (`HEADING_STYLES`, the layout's `KEEP`, the `SCHEMES` constant, creates' textarea, three copies of object words), linked title boxes, steps A–I and guard tests; class diagram `text-structure-architecture.svg` | 2026-11-16 |
| `e10-15-grid-and-snap.md` | E10.15: the view-only grid vs. the object's own persisted snap state, the mock-up's four open points, and what snapping does to an aspect-locked resize | 2026-11-07 |
| `e5-1-e5-10-menus-and-accessibility.md` | The menu-schema redesign (UX-06/UX-09), the UX-01/03/04/05 accessibility baseline, and the dark-mode contrast/About-dialog/button-shape bugs found running the patch, with `mockups/`; a patch exists, not yet committed (PROC-03: not built) | 2026-11-05/06 |
| `bitv-scorecard-2026-11-13.md` | An estimate of where the web app stands against BITV 2.0 / WCAG 2.1 AA, by principle (about 59 of 100 today, about 70 with an accessible grid), the user groups to weigh it by, the order of work, and what the quick fixes on branch `bitv` did and left | 2026-11-13 |
| `bitv-grid-and-alt-text-2026-11-13.md` | The accessible grid (UX-02) and alt text with decorative objects (UX-31) built on `bitv`: structure, focus, the live region, what axe found, the model and export for descriptions, what was not verified; mock-up `mockups/describe-object-and-grid-structure.svg` (built before it was agreed) | 2026-11-13 |
| `code-map.md` | The narrative map of the repository, **stale**: written at `842d739`, six packages | 2026-11-02 |
| `code-review-2026-11-15.md` | Review for duplication, separation of concerns, naming and convoluted code at `7994b00`: the picture, measurements, order of work and open questions; items CODE-27 to CODE-41 in `bugtracker.md` | 2026-11-15 |
| `composes-tables.md` | Proposal (nothing built, no decision numbers): tables in composes as an object whose body points at a `TableDef` in `claudia_core`, the `TableSource` protocol shared with computes named ranges, computes-versus-composes comparison, in-flow default with floating as a second placement, cells as paragraphs, numbers as text, no formulas, totals, sorting, collaboration, linked tables, files, layout, slices S0–S6, disagreements and open questions (E9.32, E9.33); mock-ups `composes-table-screens.svg`, `composes-table-architecture.svg` | 2026-11-18 |
| `styling-system.pdf` | How styles work, for people: the idea (a style says what something is for, D306), the words (style, purpose, facet, style kind, slot, palette colour, number format), a text box's two slots and the facets they read, which style fits which slot, what a style is not (one per thing, a number format, direct formatting), how styles share and the open question D1412, and what follows for the code (E1.14–E1.19); source `styling-system.html`, figure included | 2026-11-21 |
| `organisations-entry-continuity-exit.pdf` | **Not decided** (proposal, no decision number): how an organisation and its members could work with documents at entry, continuity and exit; the atlas (the organisation's places), the steward key slot (visible, two custodians, a last resort), the hand-over wizard; what exists today and what would be new; open questions including more than one owner. Reconstructed from sheet 7 of the conversation of 2026-11-14; source `organisations-entry-continuity-exit.html` | 2026-11-21 |
| `bug-eater.md` | The brief of the bug-eater chat: its four tracks (bugs, architecture, domain language, tests), the batch loop from branch to marking items fixed, helpers (two sub-agents, Fable as advisor); its queue is `bug-eater-queue.md` | 2026-11-24 |
| `bug-eater-queue.md` | The triage of every open tracker item against `backlog` at the time it was written: still real or not, class, cluster, size, the failing test to write first, and the proposed batches | 2026-11-24 |
| `menu-audit.md` | Menu audit, phase 1: the workbook `claudia-menus.xlsx` against the menus of all three apps on web and desktop; how `scripts/menu_capture.py` and `scripts/menu_audit.py` make the workbook's Diagnosis sheet, the picture, the bugs found, what could not be run | 2026-11-25 |

## Three documents were deliberately not copied

`code-map-api.md`, `src-core-interfaces.md` and `src-server-ai-and-apps.md` are not here, and this is a judgement
rather than an omission — say so if you want them anyway.

- `code-map-api.md` is a **generated** listing of every module, class and function, produced by `codemap.py` from
  commit `842d739`. It is derived data with a generator, and it was already stale the day the next commit landed.
- `src-core-interfaces.md` and `src-server-ai-and-apps.md` are **literal copies of source files** that are in the
  repository. A second copy in a notes folder cannot be kept true and competes with the real thing; the Sphinx site
  (E11.5) is the generated API reference and does not go stale.

What was worth keeping from them is the generator, so it is preserved in `code-map.md` as a code block. It needs two
changes before it is useful again: the package list is still the six of `842d739` and should read the uv workspace
members from `pyproject.toml`, and it belongs in `scripts/codemap.py` next to `check_debt.py` and `api_surface.py`
rather than in a notes folder. That move is left as a recommendation because this round's patch stays inside
`claudiaoffice-log/`.

## How to use these

They record *what was built and what was not*, including the things that did not work. The "not verified" and "known
limitations" sections are the valuable part and should not be trimmed when a note is updated.

One rule added after this round (see PROC-03 in `bugtracker.md`): **a note may only say a thing is built when a commit
carries it.** `e4-e6-formulas.md` claimed a feature that exists in no commit on any branch, and the claim survived
because nobody checked it against the tree. Status belongs in the backlog (`Projects/claudia-office/_tasks/`) and is derived from the code.
