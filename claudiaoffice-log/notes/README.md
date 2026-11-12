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
| `e4-e6-formulas.md` | The formula engine as built, the proposed decisions, and what was measured | 2026-11-03 |
| `e5-linux-client.md` | The GTK shell, the shell contract, the menu mapping, and the compatibility notes | 2026-11-03 |
| `e7-ai.md` | The `ai` user design and the E7.1 port: packages, decisions taken while porting, what is unverified | 2026-11-01/02 |
| `e7-ai-agent-design.md` | Proposal: the AI sees the document and the effect of its actions (read tools, effect report, loop), the local model in all three apps (composes fails, creates has none), Claude as a provider in the server settings; decided D261–D266 (rights of the asker, act/suggest per person with suggest as default, proposals as scratch previews, two opt-ins for a remote AI, an acting AI for creates, Claude by API key); mock-ups `ai-settings-provider.svg`, `ai-panel-observe-act.svg`, `ai-suggest-mode.svg` | 2026-11-11 |
| `e9-composes.md` | The composes model, the web demo history, and the styling work | 2026-11-02/03 |
| `e9-print-and-layout.md` | E9.4/E9.6/E9.14/E3.3 on branch `layouting`: the `@claudia/layout` library part by part and what the other apps reuse, the print preview, fonts for clients, choices made while building, measurements, and what was left for E9.23, E9.24, E6.19, E10.18 (D901–D911); mock-up `mockups/print-preview.svg` | 2026-11-12 |
| `e10-15-grid-and-snap.md` | E10.15: the view-only grid vs. the object's own persisted snap state, the mock-up's four open points, and what snapping does to an aspect-locked resize | 2026-11-07 |
| `e5-1-e5-10-menus-and-accessibility.md` | The menu-schema redesign (UX-06/UX-09), the UX-01/03/04/05 accessibility baseline, and the dark-mode contrast/About-dialog/button-shape bugs found running the patch, with `mockups/`; a patch exists, not yet committed (PROC-03: not built) | 2026-11-05/06 |
| `code-map.md` | The narrative map of the repository, **stale**: written at `842d739`, six packages | 2026-11-02 |

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
