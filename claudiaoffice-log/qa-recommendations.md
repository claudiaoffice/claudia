# QA review — 2026-11-12

Repository `claudiaoffice/claudia` at `7e619a2` ("Merge pull request #28 from claudiaoffice/ai_server"), every feature
branch merged; the patch was then moved onto `d696927` (the Windows client rework merged on top) and re-run there. Reviewer: QA role. Previous rounds: 2026-11-02 (`f8df891`), 2026-11-05 (`54d1245`, this file's earlier
version, in git), 2026-11-10 (`301ded6`, `implementation-notes/implementation-notes-qa-2026-11-10.md`). Every finding
has an entry with evidence and acceptance test in `bugtracker.md`; this file gives the marks and the order of work.

**Aim of the round:** a stable intermediate version — documented, integrated, tested, CI green — not new features.

---

## What was run

| Check | At `7e619a2` | With this round's patch |
|---|---|---|
| `check_debt.py --ci` (CI's Python job) | **failed**: tests (CHANGELOG 0.13.0 twice), docs (3 unresolved refs) | passes |
| `pytest` | 4,052 passed, 1 failed, 9 skipped | 4,112 passed, 8 skipped, 0 failed |
| Linux client, Python 3.12 + GTK 4 + WebKitGTK 6.0 under Xvfb | **1 failed** (e2e race) | 558 passed, 6 skipped (also under the new CSP) |
| `odf_libreoffice_check.py` with LibreOffice 24.2 | **crashed** building its deck | 31 of 31 read by LibreOffice |
| `tests/e2e` (three servers, real browser) | passes | passes |
| `web/e2e/*.cjs`, seven browser scripts | **2 failed** (demo: AI inert; styling: stale selector) | all 7 pass |
| web: eslint, vitest + coverage, `nuxt typecheck` | pass | pass |
| `web/e2e` Windows and macOS shell windows (Neutralino faked, real frame) | — (added in `d696927`) | pass, also under the new CSP |
| Under the new CSP (SEC-13): a Plotly chart, the settings page, an injected inline script | — | chart and page work, the injected script is refused, no other report |
| `npm audit` (SEC-08) | clean | clean |
| Coverage floors | all held | all held; seven floors raised (composes 83 → 88 with the new tests) |
| `./start.sh all`, `./start.sh --ai` | ran | ran: OpenVINO GenAI installed by the launcher, the model folder handed to computes only |

Browsers: Chrome for Testing 153 (no Firefox here). Not run: Windows/macOS clients, a real language model (no
download possible from this machine), the live demo.

---

## Marks (1 very good … 5 needs rework, prio)

| Area | Mark | Previous (11-05) | In one line |
|---|---|---|---|
| **UX and UI: consistency and usability** | **3** | 4 | Accessibility moved for real (keyboard menus, native dialogs, dark mode, contrast); what now costs is consistency between the three apps, and an AI that promised what it could not do. |
| **Code quality and technical debt** | **2** | 2 | Still unusually disciplined (one gate, ~4,650 Python and 655 web tests, typed, API-snapshotted, coverage floors, low complexity); the debt is in *merging*: four CI failures came only from branches meeting, and the tracker lags the code. |
| **Security** | **4** | 3 | The container, sandbox and AI dispatch are sound, but the new server-settings surface has a P1: the first anonymous visitor of an exposed server becomes its administrator (SEC-12). |
| **Performance** | **2** | 3 | The two measured hot paths (PERF-01, PERF-05) are fixed and guarded: a grid window is O(window), the extent O(1). Left: per-edit `fsync` on the event loop with a worker pool that nothing uses. |
| **Gaps, computes** | 3 | — | Formulas, names, SQL, charts, images, ods/xlsx export: a real spreadsheet. Missing the Bret Victor half (live controls, dependencies, what-if) and an accessible grid. |
| **Gaps, composes** | 3 | — | Styles-first editing and suggestions are the best-designed flow in the suite. No layout/pagination, no model-driven AI (stand-in only), no import. |
| **Gaps, creates** | 4 | — | Slides, boxes, three shapes, images, odp/pptx export. No AI, no presentation mode, no templates/layouts; the chat advertises an `@ai` that does not exist. |
| **Overall, for a pre-release** | **3** | 3 | A healthier 3: CI can be green, the AI works again, and the remaining P1 is small and well understood. |

### UX, in more detail

Fixed since 11-05, re-checked in this tree: UX-01 (menu keyboard and ARIA), UX-03 (native `<dialog>`), UX-05 (dark
mode with system default and override), most of UX-04 (all neutral text ≥ 4.5:1, field borders ≥ 3:1 in both themes).
Still open: **UX-02**, the grid has no row/cell structure for a screen reader — the single biggest accessibility gap,
because the grid *is* computes.

New, from looking at the three apps side by side:

* **UX-20 (P1, fixed):** since the act/suggest merge, `@ai` in computes always answered "Switch to act mode" — a switch
  no client has. The server read a missing mode as *suggest*, against its own method description. Fixed as agreed.
* **UX-21:** creates' chat says "@ai to ask the assistant" with no AI in the document; a hint must come from what the
  server says is there.
* **UX-22:** three history dialects: `ann A1 = Item` / `ann typed "…"`, `style title` / `Added a text box`, `Add shape`.
  One rule (past tense, lower case, names not ids) and a test per app.
* **UX-23:** composes puts its suggestions above the panel tabs, the others put tabs on top; undo/redo sit in three
  different places. The decided History filter row (All / Conversation / Changes) is not built.

Visual design on its own stays a 2: the palette, the type and the three-app identity hold, and the styling dialog is
still the most thoughtful interaction in the suite.

### Code quality, in more detail

What is good and should not be "fixed": the gate (`check_debt.py`) that CI and laptops share; coverage floors that
only go up; the public-API snapshots; vulture with a reasoned whitelist; docstrings that explain decisions; McCabe
complexity — only six functions in all of `packages/*/src` exceed 12, none exceeds 16.

What cost this round, and why it is process rather than code:

* **Parallel branches collide on the same numbers.** Two branches released claudia-core 0.13.0 (PROC-09); one branch
  added types to a signature that the docs branch never listed (PROC-10). Rule: *the version and the API reference are
  the last thing a branch touches, after merging `main`, and the gate runs after that merge*.
* **A check that may fail is a check nobody reads.** The LibreOffice job is `continue-on-error`, so its crash went
  unseen (PROC-11). Now its model-building half runs in the normal suite.
* **The tracker drifts.** Five fixed items were still "verified open"; E7.7 was `todo, 0 %` with a "built" paragraph;
  64 of 90 in-progress stories sit at exactly 50 % (PROC-15).
* **Built but not wired:** `WorkerPool` (E3.5) is created and stopped by every hub and called by nothing (CODE-13).
* **Two copies of one shell:** since `d696927` the Windows client follows the macOS design and has its features, by
  copying — 11 of 22 source files are byte-identical in both (CODE-14). Move them into one shared package; until then
  a test that keeps the copies identical.

### Security, in more detail

* **SEC-12 (P1, recommendation only, as agreed):** `POST /api/admin/setup` on an exposed server with no administrator
  is open to anyone, even with `CLAUDIA_ACCESS_SECRET` set — reproduced. Fix: a one-time setup code printed in the
  server log and required by `setup` (plus the access secret when set); one field in `FirstAdminSetup.vue`.
  Mitigation for the demo now: claim the administrator right after each deploy, or block `/api/admin/` at the proxy.
* **SEC-17 (P2):** a viewer's live connection receives the history and chat the container withholds from her. Found
  on 11-05, never numbered, so never picked up.
* **SEC-13 (P2, fixed in this patch):** there was no CSP / `frame-ancestors` / `nosniff` / `Referrer-Policy`. Now
  every answer has them; scripts are allowed by hash, framing only by the desktop shells' local page (D251).
* **SEC-15 (P2, P1 when import ships):** the office readers read every zip part whole and three call sites parse XML
  with lxml defaults; harden before the import UI sends a file.
* **SEC-14, SEC-16 (P3):** Swagger UI from a CDN; any executable accepted as "xelatex".
* Still open from earlier rounds: SEC-05 (redaction leaves bytes), SEC-06 (certificate is an unconstrained CA), SEC-11
  (no login back-off, now also for administrators), SEC-08 half (`pip-audit`).

### Performance, in more detail

Re-measured: a 64×16 grid window costs 0.06–0.11 ms from 10k to 500k cells (was 21 ms at 500k); the extent is 0.001
ms (was 38 ms). Both guarded. Open: PERF-02 (an `fsync` per edit on the event loop), PERF-06 (packing on the loop),
PERF-07 (structure edits recalculate everything), PERF-08 (the first chart loads 4.6 MB of Plotly for a bar).

---

## Recommendations, in order

Each one is a bugtracker entry with evidence, a fix and an acceptance test; pick it up from there.

| # | What | Items | Who | Size |
|---|---|---|---|---|
| 1 | Close the administrator bootstrap: setup code + access secret; then login back-off | SEC-12, SEC-11 | server dev + one field (designer: mock-up) | 1–2 days |
| 2 | Withhold history and chat from viewers on the wire | SEC-17 | server dev, product call on public chat | 1 day |
| 3 | The act/suggest switch in the three clients, from `notes/mockups/ai-suggest-mode.svg`; chat hints from what the server has | E7.7, UX-21 | web + shells | 2–3 days |
| 4 | ~~Security headers on the web app~~ — **done in this patch** | SEC-13 | | |
| 5 | Journal append and packing off the event loop; wire or remove `WorkerPool` | PERF-02, PERF-06, CODE-13 | server dev | 1–2 days |
| 6 | One phrasing rule for the history, and one panel layout and undo place across apps | UX-22, UX-23 | designer first (mock-ups), then web | 2–3 days |
| 7 | Accessible grid (`row`/`gridcell`, `aria-activedescendant`), with the E5.10 baseline | UX-02, E5.10 | web | 3–5 days |
| 8 | Harden the office readers before import goes on the wire | SEC-15 | io dev | 1 day |
| 9 | One shared Neutralino core for both shells, or a test that the copies stay identical | CODE-14, E5.11 | shell dev | 1–2 days |
| 10 | Merge rule (version and API docs last, gate after merging `main`), tracker hygiene, `progress: 50` check | PROC-09, PROC-15 | everybody / gate | ½ day |
| 11 | Small ones: Plotly partial bundle (PERF-08), Swagger off by default (SEC-14), typeset program check (SEC-16), creates' `--app-dark` contrast (UX-04) | | | ½ day each |

### Gaps and edge cases, per app

**computes.** Built: sheets, formulas (Excel syntax, growing library), names and structured references, `SQL()`
spilling, bar charts, images on the object layer, styles by purpose, ods/xlsx export. Gaps: live controls, dependency
view, what-if (E6.10, E6.11, E4.8 — the Bret Victor core of the vision); number and date formats (E6.14); the AI can
act but not propose (E7.8), so *suggest* refuses; import of ods/xlsx is not on the wire; the grid is not accessible
(UX-02). Edge cases to test next: structure edits on a sheet with spilled `SQL()` results and charts reading them;
undo of a structure edit that another person's formula depends on.

**composes.** Built: paragraphs, styles first with an invitation to name, deviations, flow/page views, authorship,
AI suggestions anchored to text, objects that follow the text (now tested), odt/docx export. Gaps: deterministic
layout and pagination (E9.4, your leaning: in the browser, deterministic); a model-driven AI (only the scripted
stand-in: no lens for texts, E7.5); import; outline view; citations (E9.15–E9.18). Edge cases: a suggestion whose
anchor paragraph is joined into another while it is open; an object anchored at the very end of a paragraph that is
split there.

**creates.** Built: slides, text boxes, circle/rectangle/triangle, images, grid and snap, styles in two slots, odp/pptx
export. Gaps: no AI participant at all (E7.9; the chat hint promises one, UX-21); no presentation mode (E10.2);
templates and layouts (E10.4); only three shapes. Edge cases: a style deleted while a shape's label uses it (guarded
by `style_in_use`, worth a browser test); objects outside the slide after a slide-size change.

**Across the suite.** Admin bootstrap (SEC-12); one AI model per app server rather than the shared AI server of D2 —
with `./start.sh all --ai` only computes loads it, because each server would load its own copy; the Windows and macOS
shells as two copies of one code base (CODE-14); the History filter row decided but not built.

---

## The things you already knew

* **A start script with the AI running:** `./start.sh all --ai` (built). It takes the one model folder in `ai-models/`
  (or `--ai MODEL_DIR`, `--ai-device CPU`), installs OpenVINO GenAI into the environment the first time
  (`uv sync --inexact --package claudia-server --extra openvino`), hands the model to computes only (composes and
  creates would refuse to start with it: they have no lens yet) and waits up to 15 minutes for the model to load
  before opening the browser. Tested up to loading; no real model could be downloaded here.
* **Document folders:** `demo-docs*` is what the script used before commit 2938f0a, `docs-<app>` after it; nothing ever
  moved the old ones. Now (agreed): `.claudia/<app>/documents` and `.claudia/<app>/state` per checkout, `--dir DIR`
  means `DIR/<app>/…` for one app and for `all`, each server gets its own state (they shared one certificate and one
  administrator list before, in the folder tree the Linux desktop app uses), and old folders are named at start with
  where to move them — never moved automatically. Left as they are, for a later decision: the server puts a `docs/`
  folder inside whatever `--dir` it gets, and its own default state folder on Windows is the roaming `%APPDATA%` while
  the Windows shell uses `%LOCALAPPDATA%`.
* **Python version:** the cause is that nothing pinned 3.14: `requires-python = ">=3.14"` lets `uv` pick 3.15 where it
  is installed, and `openvino-genai` publishes only cp314 wheels (no sdist) in `uv.lock`. `.python-version` now says
  3.14 and a test keeps it, every package's floor, CI, the Dockerfile and the Debian build in step. The server needs
  **3.14** exactly for now; the Linux desktop shell itself runs on the distribution's Python ≥ 3.12.

## What this round's patch contains

Security: SEC-13, CSP and the other security headers on every answer of the three apps' servers. CI: PROC-09 to
PROC-14 and PROC-16 (a flaky undo timing guard) fixed (changelog renumbered to 0.15.0 with snapshot, docs references, LibreOffice script and
a test for it, Linux e2e wait, Python pin with a test, stale e2e selector). Behaviour: UX-20 (missing AI mode = act),
the launcher's AI option and folder layout (CODE-15). Tests added: objects following text in composes, the server's
default state folder and private files, the launcher's new options. Tracker: statuses re-checked, 22 new items. No
other behaviour changed.
