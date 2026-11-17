# Follow-up 2026-11-17: CODE-58, CODE-60, PROC-27

On top of `7fe03c7`. CODE-58 (creates exporters report the style properties they cannot write), CODE-60 (default styles
generated for layout and web, one `ObjectKind`, one leader geometry, drift tests) and PROC-27 (pinned actions,
`latest` only after CI, CodeQL, `pip-audit`) are fixed (D760–D762); CODE-63 is new. Marks unchanged except: code quality
stays 2, security 3 (supply chain better, SEC-11/19 open). Not seen: the first runs of the new workflows, the browser e2e.

---

# QA review — 2026-11-17 (stabilisation of `main`)

Repository `claudiaoffice/claudia` at `f150f0d`, all feature branches merged, nobody committing meanwhile. Reviewer: QA
role. **Aim:** a stable intermediate version, no features. Every finding is in `bugtracker.md`, section "Round of
2026-11-17" (PROC-24 to PROC-27, CODE-58 to CODE-61, SEC-19, UX-44; SEC-15 fixed). The previous round (11-13) is below.

**What was run:** a fresh checkout, `scripts/check_debt.py --ci` (ruff, format, mypy, vulture, i18n, menus, ~7,300
pytest tests with coverage floors, npm audit, layout and web lint/tests/types, Linux client). **Not run here:** the
Chromium e2e job (the web app cannot be built and driven in this environment), GitHub Actions history (no `gh` access),
Firefox, screen readers, Windows and macOS clients, a real language model.

## Marks (1 very good … 5 needs rework, prio)

| Area | Mark | Previous | In one line |
|---|---|---|---|
| UX and UI consistency, usability | **3** | 3 | Same menus and dialogs across the apps; the differences left are the AI mode switch (UX-34, UX-37), history dialects (UX-22) and panel layout (UX-23). |
| BITV (WCAG 2.1 AA) | **3** | not graded | Grid structure, focus order, contrast, descriptions and a document-named title are in; open: landmarks (UX-32), dialog focus and menu keyboard use to re-verify, reduced motion fixed (UX-44). Measured by script and reading only, not with a screen reader. |
| Code quality, technical debt | **2** | 2 | One gate, typed, coverage floors. Debt: facts written twice (CODE-60), flat `claudia_server` (CODE-29), 1,100-line `computes.py` (CODE-21), copied web write calls (CODE-35). |
| Architecture | **2** | n/a | Pure kernel, thin clients, one wire. Deviation from best practice: the web repeats server facts instead of receiving them (CODE-60), and CPU work shares the event loop (CODE-13). |
| Security | **3** | 3 | Import is now bounded and parsed safely (SEC-15 fixed). Open: SEC-06, SEC-11 (raise to P2 while the demo is public), SEC-14, SEC-16, SEC-17, SEC-19, unpinned actions (PROC-27). |
| Performance | **3** | 3 | Guards exist and pass. Open: PERF-01, 02, 05, 10; imports have no memory cap (SEC-19). |
| Gaps, computes | **2** | 2 | Strongest app. Missing: print, AI proposals, new sheet reusing a removed id (CODE-56). |
| Gaps, composes | **3** | 3 | No outline view, no search; exporters write what the model has. |
| Gaps, creates | **3** | 3 | Exporters silently drop style properties (CODE-58); pptx import without placeholders, sizes and colours (CODE-45, 46); no layouts or presenter mode. |
| Overall | **3** | 3 | `main` is green again; the gap to a stable intermediate version is CI hardening (PROC-27) and drift (CODE-60). |

## Recommendations, in order (each is picked up from its bugtracker entry)

1. **Gate merges on `check_debt.py --fast`** and give each branch its own decision/story range (PROC-24).
2. **CODE-58:** report or write the dropped style properties in the creates exporters.
3. **CODE-60:** the server sends style flags and the object-kind set; web and layout read them; a drift test.
4. **PROC-27:** SHA-pinned actions, `latest` only from green CI, CodeQL, `pip-audit`.
5. **SEC-19** and **SEC-11:** import in a limited worker; back-off for failed logins.
6. **UX-34, UX-37:** decide the AI mode behaviour once for all three apps.
7. **CODE-61:** set the stale backlog statuses; **CODE-29/21:** split `claudia_server` and `computes.py` as agreed.

## What this round's patch contains

SEC-15 (zip limits and one hardened XML parser, with tests); PROC-24 (main's two red tests); PROC-25 (deploy gated on CI);
PROC-26 (dependabot); CODE-59; UX-44; coverage floor for claudia-fonts raised to 98; tracker updated. No behaviour was
added.

---

# QA review — 2026-11-13

Repository `claudiaoffice/claudia` at `cfa2d91` ("Accessibility improvements, especially in grid of computes"), every
feature branch merged: printing in composes and creates with the layout library, lists and anchors, search and replace
with the pattern builder, random numbers and scenarios, the i18n push, the BITV fixes. Reviewer: QA role. Previous
rounds: 11-02, 11-05, 11-10, 11-12 (this file's earlier versions, in git). Every finding has an entry with evidence, a fix
and an acceptance test in `bugtracker.md` (section "Round of 2026-11-13"); this file gives the marks and the order of work.

**Aim of the round:** a stable intermediate version — documented, integrated, tested, CI green — not new features.

---

## What was run

| Check | At `cfa2d91` | With this round's patch |
|---|---|---|
| `check_debt.py --ci` (CI's Python job, all three OSes) | **failed**: 1 test (PROC-18) | passes, with the Linux client and the e2e greeting |
| `pytest` | 4,875 passed, **1 failed**, 9 skipped | 4,904 passed, 2 xfailed (SEC-18), 9 skipped (Windows-only, OpenVINO) |
| `web/e2e`, 18 browser scripts | **`demo.cjs` failed** (PROC-20); 6 scripts not in CI | all 18 pass, in CI's order, all now in CI |
| `tests/e2e` (three servers, real browser) | passes | passes |
| Linux client, Python 3.12 + GTK 4 + WebKitGTK 6.0 under Xvfb | **1 failed** (PROC-20) | 572 passed, 6 skipped |
| Windows client: vitest, types, build, menu check | pass (335) | pass |
| macOS client: vitest, types, build | pass (333) — but **run by no CI job** | pass, now a CI job |
| web: eslint, vitest + coverage, `nuxt typecheck` | pass (952 tests; app/lib 88 % statements) | pass |
| layout library: types, tests, TypeDoc | pass (115 tests; 2 TypeDoc warnings) | pass |
| `odf_libreoffice_check.py`, LibreOffice 24.2 | 31 of 31 | 31 of 31 |
| `npm audit` / `pip-audit` (by hand) | clean / clean | — |
| Coverage floors | all held | all held |

Browsers: Chromium 153 only (no Firefox here). Not run: Windows/macOS on their own systems, a screen reader, a real
language model, the live demo, the Docker image (no daemon: Dockerfile read only).

**CI was red at `cfa2d91` in three jobs** (Python on all OSes, e2e, Linux client) — the same shape as last round:
each branch was green alone, the merge broke tests that belong to another branch.

---

## Marks (1 very good … 5 needs rework, prio)

| Area | Mark | Previous (11-12) | In one line |
|---|---|---|---|
| **UX and UI: consistency and usability** | **3** | 3 | Accessibility took a real step (grid structure, F6, descriptions, contrast all merged); the cost is now integration: the AI refuses by default in two apps, new features missing from the desktop menus, a third of the menu without shortcuts. |
| **Code quality and technical debt** | **2** | 2 | The code is still disciplined (one gate, ~7,200 automated tests, typed, coverage floors, docstrings that explain decisions). The debt is structural: CPU-heavy work lands on the event loop because the worker pool has no callers, and merges keep breaking CI. |
| **Security** | **3** | 4 | SEC-12 is now your conscious decision and not counted. New P1: a search pattern that slips past the static guard freezes the whole server for anybody with access to one document (SEC-18). SEC-17 and SEC-15 still open. |
| **Performance** | **3** | 2 | Two new features do seconds of work synchronously: what-if outcomes (9 s per edit in a 1,000-cell model, PERF-10) and search (SEC-18). Webfont generation (up to 37 s on the loop) fixed in this patch. |
| **Gaps, computes** | **2** | 3 | Random numbers, scenarios with outcome distributions, Follow, search & replace with a builder, an accessible grid: the Bret Victor half has arrived. Missing: print, AI proposals, number/date formats, import on the wire. |
| **Gaps, composes** | **3** | 3 | Print with deterministic pages and lists landed. Still a stand-in AI, no import, no outline view, no search. |
| **Gaps, creates** | **3** | 4 | Print, descriptions, the style picker. No templates/layouts (the core of the vision for creates), no presenter mode, the AI acts only and refuses by default. |
| **Overall, for a pre-release** | **3** | 3 | Feature-wise the best state so far. To call it a stable intermediate version: green CI on `main`, SEC-18, UX-34. |

### UX, in more detail

Re-checked as merged and working (browser scripts pass): UX-02 grid structure, UX-04 contrast, UX-28 to UX-31.

New, from using the three apps side by side (screenshots in the chat of 2026-11-13):

* **UX-34 (P1, needs decision):** D262 makes *suggest* the default; only composes can propose. In computes and creates
  every change the AI is asked for is refused until the person finds the switch.
* **UX-33:** a new workbook's first Ctrl+Z removes its only sheet ("This document has no sheet yet."); a new text or deck
  offers "Undo Language".
* **UX-36:** Print, lists, the hyphen characters, Image, Chart, Names, SQL, Clear Cell Style, View ▸ Grid are on the web
  menus but not on the desktop menus — and the desktop shells hide the web menu bar.
* **UX-35:** 30–37 entries per app have no shortcut (rule: every entry has one). Needs one key table from design first.
* **UX-37:** composes offers an act/suggest switch that changes nothing.
* Still open: UX-22 (three history dialects — "add sheet Sheet1", "set the language to en", "undo · remove a sheet"),
  UX-23 (undo/redo buttons in computes' and creates' bars, none in composes; "History & chat" vs "History & Chat").

### Code quality, in more detail

What is good and should not be "fixed": the gate shared by CI and laptops; the guards on decisions, backlog and notes;
the pattern builder's design (one engine on the server, D284); the deterministic layout library with pinned WASM and
fonts; the i18n pipeline (1,476 strings, German complete).

What costs:

* **The worker pool (CODE-13) is the missing piece.** SEC-18 and PERF-10 are both "CPU work that cannot be stopped,
  on the event loop". D284 even says "runs in the worker pool"; the as-built note replaced that with a heuristic.
* **Merging breaks CI, again** (PROC-18, PROC-20). Every branch was green on its own.
* **Search is computes-shaped** (CODE-18): the panel and protocol say `{sheet, row, col}`, though the panel is meant for
  all three apps. Cheaper to change before composes and creates use it.
* The Windows and macOS shells now share 14 identical files (CODE-14, was 11).

---

## Recommendations, in order

Each one is a bugtracker entry with evidence, a fix and an acceptance test; pick it up from there.

| # | What | Items | Who | Size |
|---|---|---|---|---|
| 1 | **Main stays green:** merge through a pull request with the CI jobs required (branch protection), or run `check_debt.py --ci` plus the e2e step after merging, before pushing | PROC-18, PROC-20 | owner | ½ hour once |
| 2 | Make the search interruptible: `regex` with `timeout=` (closes D287 too) or the worker pool; keep the guard as early feedback | SEC-18, PERF-11 | server dev | 1 day |
| 3 | The AI default in computes and creates: decide among (a) proposals first, (b) switch disabled with a line until then, (c) per-app default | UX-34, UX-37 | owner decides; web dev | ½ day for (b) |
| 4 | Put the worker pool to work: outcomes computed off the loop and sent as their own event | PERF-10, CODE-13 | server dev, web dev | 2 days |
| 5 | A new document has nothing to undo: first sheet and language as part of creating it | UX-33 | server dev, web dev | 1 day |
| 6 | Desktop menu parity, then one key table for all three apps | UX-36, UX-35 | shell dev; designer for the key table | 1 + 1 days |
| 7 | An opaque location in search before composes and creates get it (API version) | CODE-18 | server dev, web dev | 1 day |
| 8 | Carry-overs that still matter: viewers get history on the wire; harden the office readers before import goes live; login back-off | SEC-17, SEC-15, SEC-11 | server dev, io dev | 1 day each |
| 9 | Small ones: LibreOffice job blocking (PROC-22), one browser variable (CODE-17), journal diagnostic out (CODE-19), pin uv in the Dockerfile (CODE-20), split `computes.py` (CODE-21), `pip-audit` in the gate (SEC-08) | | | ½ day each |

### Gaps and edge cases, per app

**computes.** Built: sheets, formulas, names and structured references, `SQL()`, bar charts, images, styles by purpose,
ods/xlsx export, random numbers with a seed and resampling, alternatives with outcome distributions, Follow, search &
replace with a builder, an accessible grid. Gaps: File ▸ Print (composes and creates have it); AI proposals (E7.8);
number and date formats; import not on the wire. Edge cases to test next: an alternative input deleted by a structure
edit while its outcomes are shown; `search_replace` into a cell that a spilled `SQL()` result covers; resample by two
people at once followed by one person's undo; a seed set in one session and the outcomes reproduced in another.

**composes.** Built: styles first, suggestions, authorship, flow/page view, deterministic pages and print, lists and
anchors, hyphenation, describe-language (D915), odt/docx export. Gaps: a model-driven AI (E7.5), import, outline view,
search (decided after computes), the references UI for anchors. Edge cases: a numbered heading list split across a page
break and printed; an anchor whose paragraph is deleted while another person's reference points to it; a language
change undone in a text with hyphenation (does the page reflow?).

**creates.** Built: slides, text boxes, shapes, images, grid, styles with a bar picker, descriptions, print, odp/pptx
export, an acting AI. Gaps: templates and layouts (E10.4, the heart of the creates vision), presenter mode (E10.2, spike
first), proposals for the AI, more shapes. Edge cases: printing a deck whose objects lie partly outside the slide; a
decorative image exported to pptx and opened in PowerPoint (the extension was written from memory, UX-31).

**Across the suite.** One undo model for setup steps (UX-33); one menu and shortcut table across web and desktop
(UX-35, UX-36); the worker pool for anything CPU-bound (CODE-13); one history phrasing (UX-22).

---

## The things you already knew

Your message ended with "Two things I already know:" and nothing after it. Send them and they get the same treatment.

## What this round's patch contains

CI and tests: PROC-18 (notes check reads build outputs from `.gitignore`), PROC-19 (six browser scripts, a macOS client
job, `layout/**` in the image and .deb triggers, with `tests/test_ci_workflow.py` to keep it so), PROC-20 (`demo.cjs`,
Linux client e2e), PROC-21 (demo domain). Performance: PERF-09 (fonts route off the event loop, with a test). Security:
SEC-18 recorded with a strict-xfail test, no fix (approach to agree). Docs: DOC-02 (launcher name). Tracker: the `bitv`
items marked merged, 21 new items. No other behaviour changed.
