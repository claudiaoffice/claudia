# QA review — 2026-11-05

Repository `claudiaoffice/claudia` at `54d1245` ("E5 desktop clients: linux first draft"). Reviewer: QA / UX-QA role.
Previous round: 2026-11-02 at `f8df891`. Companion files: `bugtracker.md` (every finding with its evidence),
`backlog.md` (143 stories with a status derived from the code), `decision-log.md`, `notes/`.

Everything below was run or read in that tree. Where a number appears, it was measured on this machine today; where a
claim is from a document rather than the code, it says so.

---

## Marks (1 very good … 5 needs rework, prio)

| Area | Mark | Previous | Why in one line |
|---|---|---|---|
| **1 · UX and UI: consistency and usability** | **4** | 3 | The suite now looks and behaves like one product, but **not one of the five accessibility findings from the last round was fixed** while the surface grew by two apps and a desktop client. |
| **2 · Code quality and technical debt** | **2** | 2 | Unusually disciplined: one gate, ~1,321 Python and 195 web tests, typed, documented from source, API-snapshotted, with mutation-tested sandbox rules — held back by a gate that reports "clean" while skipping, and by a note that claimed work nobody committed. |
| **3 · Security** | **3** | 4 | A real, conservatively built encrypted container replaced the plain journal and five findings are genuinely closed; what remains is that **two stated privacy promises are not enforced in code**, plus a new authorisation gap around the AI. |
| **4 · Performance** | **3** | 3 | The new calculation engine is incremental, indexed and guarded — good work — but everything still runs on one event loop, and two hot paths were measured blocking it. |
| Feature set and product fit | 3 | 3 | Three apps, formulas, styles, encryption and a native client now exist; the signature Bret Victor features (sliders, what-if, dependency views) and every interchange format still do not. |
| Architecture | 2 | 2 | Log-as-truth kernel, a purity test that has held through four epics, Region, per-document auth, a protocol table, a versioned shell contract. One unverified bet (Neutralino) and one misplaced boundary (the AI's). |
| **Overall, for a pre-release product** | **3** | 3 | A stronger 3 than last time: the foundations got substantially better, the same classes of gap stayed open, and the work is now spread across enough surface that the gaps cost more to close. |

### Why UX went from 3 to 4

Not because anything got worse. UX-01 (menus unusable by keyboard), UX-02 (the grid has no accessible structure),
UX-03 (dialogs do not manage focus), UX-04 (contrast failures) and UX-05 (no dark mode) were all reported on
2026-11-02 and **all five are still open, unchanged, in the same files**. Meanwhile composes, creates, the styling
dialog and a GTK client were added, so the same defects now span roughly three times the surface, and a sixth
appeared: the web app has six menus where D4 decided four, and the Linux shell bridges the two by clicking the web
app's menus through an injected script (UX-09).

The product names public administration and schools as an audience (D69). In the EU those buyers normally have to meet
WCAG 2.1 AA through EN 301 549 — in Germany BITV 2.0. On that bar the product is not shippable to its stated market,
and the distance grows with every screen.

Visual design alone would be a **2**: the palette, the typography and the three-app identity are distinctive and
coherent, the in-product honesty is good ("Formulas are not there yet: this is kept as text"), and the styling dialog
is a genuinely thoughtful piece of interaction design. Accessibility alone is a **5**.

### Why security went from 4 to 3

Five of the nine findings from the last round are closed and were re-verified today: DNS rebinding, unbounded document
creation, hashing on the event loop, the timing oracle, and plain-text passwords off loopback. More importantly the
plain JSON journal was replaced by a container whose cryptography is conservative and correct in shape — Argon2id with
parameters bounded against a hostile file, HKDF with a distinct label per purpose, AES-256-GCM with a fresh random
nonce and additional data naming document, domain and position, a hash chain with a head record that detects a
changed, swapped, moved or truncated block, and a reader that defends against zip bombs and path tricks. The
typesetting sandbox is the best-tested code in the tree: its rules are verified by *mutation*, so weakening a flag
makes six tests fail.

It is a 3 rather than a 2 because two promises the product makes are not true in the code:

- **"Viewers read the document but not its history or chat" (D34, E2.4).** The file enforces it — a viewer's key
  cannot open history or chat blocks. The live session does not: `HostedDocument._audience` filters by author, by
  chat recipient and by sender, and never by role, so **a connected viewer receives every command, history entry and
  chat message.**
- **"Redaction of history must be possible" (D21).** `Document.redact` changes the live state and the replayed log.
  The container never rewrites blocks or the journal, so the bytes stay in the file (SEC-05).

Plus SEC-10, below.

---

## The five recommendations

Ordered by what I would do first. Each is scoped so somebody can pick it up from this text. Every one follows
`CONTRIBUTING.md` rule 1: **the failing test comes first.**

---

### 1 · Move the AI's method allow-list out of the model's output parser and into dispatch

**Category:** security (and architecture). **Bug:** SEC-10. **Stories:** E7.6, E7.4, E9.9. **Size:** small — about a
day. **Do it before E7.5.**

**What is true today.** `apps.MODEL_METHODS` is `{"computes": ("set_cells", "add_sheet", "structure")}`, and it
decides which tools are *described to the model in the prompt*. The only thing that stops the model asking for
something else is `Agent._take_calls` in `claudia-ai`, which drops a request whose name is not in that set — a filter
applied to generated text, inside the AI library. Below it:

- `Assistant._call` calls `hosted.methods.dispatch(context, method, params)` with **no allow-list**.
- `protocol.py` contains **zero** `account.system` checks, and the generic write method `apply` decodes and executes
  any command as the calling account.
- `composes.py` guards `replace_text` and `set_style` against the assistant — and `apply` walks around both, because
  it is inherited from the core table.
- There is no `MODEL_METHODS` entry for composes at all; a composes assistant is stopped only because `Agent` ends up
  with an empty allowed set.

**Why now, rather than later.** Nothing is remotely exploitable today: every engine in the tree is trusted in-process
code. Two scheduled stories change that, and they are the next two AI stories.

- **E7.5** puts document content into the prompt. From that moment a sentence typed into a spreadsheet cell can
  propose method names, and the only thing between it and the document is a regex-extracted JSON block checked
  against a name set in a client library.
- **E3.6 / D8** moves the engine to another machine. The "engine" then becomes a socket, and `Step` objects arrive
  from outside the process.

It is also the cheapest it will ever be: there are three engines and one dispatch point.

**What to change.**

1. Give the account the set of methods it may call. `Account` already distinguishes `system`; add the permitted
   method names to it (or to `Context`), set from `MODEL_METHODS` when the assistant account is made.
2. Check it in `MethodTable.dispatch`, before the method function runs, raising `RequestError("forbidden", …)`. This
   is the one place every path goes through: `Assistant._call`, the wire, and any future remote AI connection.
3. Add an `account.system` check to the generic `apply` in `protocol.py`, so the assistant cannot reach through it a
   command whose wrapper method would refuse it.
4. Add a composes entry to `MODEL_METHODS`: `("suggest",)` and nothing else.
5. Keep `Agent._take_calls` as it is. It stays useful as an early, friendly message to the model; it just stops being
   the thing the guarantee rests on.

**Tests to write first.**

- An `Assistant` whose engine returns `Call("apply", …)` is refused with `forbidden` and the document is unchanged.
- The same for `Call("chat", …)`, `Call("undo")` and `Call("save_checkpoint", …)`.
- A composes assistant may call `suggest` and is refused `replace_text`, `set_style` and `apply`.
- A person's connection is unaffected: an editor may still call `apply`.

**Done when** E7.6's acceptance criterion can be written as a passing test: no protocol method reachable by `ai`
writes outside its allow-list.

---

### 2 · Make the project's own quality signals tell the truth

**Category:** code quality and technical debt. **Bugs:** PROC-02, PROC-03, DOC-01, CODE-07, CODE-08. **Stories:**
E11.4, E11.1, E11.6. **Size:** small — one to two days for all of it.

This is first-among-equals with #1, and it is cheap. Every other decision on this project is made by reading the
gate's verdict, the notes and the decision log. All three currently mislead, in three different ways, and I found each
one by accident rather than by looking for it.

**(a) The gate says "clean" when it skipped checks.** Measured today in a fresh clone: the gate printed
`web tests: skipped`, `web types: skipped`, then **"Technical debt check: everything is clean."** and exited 0. There
is no `--ci` flag, and `.github/workflows/ci.yml` calls `check_debt.py` with no arguments, so **the Python job on all
three operating systems skips the web checks and still reports clean**. The separate `web` job does run them on
ubuntu, so the checks are not lost — but the gate's own verdict is untrue, and the Linux-client tests skip the same
way wherever `/usr/bin/python3` lacks pytest and jsonschema.
*Fix:* print `clean except skipped: …`; add `--ci`, which turns a skip into a failure; have CI pass `--ci`, listing
the genuinely platform-specific skips explicitly. *Test first:* with no `node_modules`, `check_debt.py --ci` exits
non-zero.

**(b) A note recorded work that nobody committed.** `e4-e6-formulas-notes.md` described point-and-click cell
references for E6.3 as built on 2026-11-03, with `web/app/lib/pointing.ts`, `web/tests/pointing.test.ts` holding 22
cases, and a nine-case browser scenario. None of it exists — not in the tree, and not in any commit on any branch:

```
git log --all -- web/app/lib/pointing.ts     →  no commits
grep -rl "REFERENCE_COLORS\|slotAt" web/     →  nothing
grep "e2e:pointing" web/package.json         →  nothing
```

The delivery model is "Claude produces a patch, the owner creates the branch and commits", and a patch can evidently
be lost in that gap without anybody noticing. The cost is not just the lost feature: the notes are what the next
decision is made from.
*Fix:* recover or rebuild the work (the design is preserved in `notes/e4-e6-formulas.md`); and adopt the rule that a
note may only say "built" with the commit that carries it, while status lives in `backlog.md` and is derived from the
code. A cheap guard: a gate line that greps the notes for file paths that do not exist.

**(c) Decision numbers mean two things at once.** D70–D82 and D97–D99 were each allocated twice, by three documents
written in parallel. It is live in the source: `claudia_container/crypto.py` cites D72, D73 and D74 meaning hidden
names, the plain manifest and the cryptographic primitives, while `claudia_server/composes.py` cites D73 and D75
meaning styling-is-CSS and the styling details. The same number, two directories apart, two meanings.
*Already done in this round:* `decision-log.md` keeps the product numbering, the container block moved to D100–D112,
the native-client block to D113–D119, and a mapping table at the top of the log makes old references resolve.
*What remains:* update the D-number citations in `claudia-container`, `claudia-server` and `claudia-creates`, and add
a gate line that fails when a `D<number>` in the source resolves to no entry or to more than one.

**(d) Two small things in the same family.** `uv.lock.rej` is committed at the repository root — rejected hunks from a
failed lock update, which also show a `cryptography` floor wavering between `>=43` and `>=44`. That is not cosmetic:
Argon2id first appears in `cryptography` 44 and the container needs it, so a `>=43` floor permits an install that
cannot open a document. And `ruff format --check .` fails today on one file while the gate never runs it.
*Fix:* delete the `.rej`, regenerate the lock, confirm the floor is `>=44`; add `ruff format --check .` to the gate;
add a line that fails if any `.rej` or `.orig` file is ever tracked.

**Done when** a green gate means every check ran, a note cannot claim an uncommitted file, and every D-number in the
source resolves to exactly one decision.

---

### 3 · An accessibility baseline for the grid, the menus and the dialogs

**Category:** UX and UI. **Bugs:** UX-01, UX-02, UX-03, UX-04, UX-05. **Story:** E5.10, feeding E12.7. **Size:**
medium — roughly a week for the four P2s, plus dark mode separately.

Four concrete defects, each in one file, each with a standard fix. They are grouped because they share one test
harness and because fixing them one at a time means re-testing three times.

**UX-02, the grid — do this one first.** `SheetGrid.vue` has exactly two ARIA attributes: `role="grid"` and
`aria-label="table"`. No `role="row"`, no `role="gridcell"`, no `aria-rowcount`/`aria-colcount`, no
`aria-rowindex`/`aria-colindex`, no `aria-activedescendant`, no `aria-selected`. A screen reader cannot say what is in
a cell or where it is. The grid is the product, and it is the one place where virtualisation makes the fix non-obvious:
`aria-rowcount`/`aria-colcount` describe the whole sheet while `aria-rowindex`/`aria-colindex` describe the rendered
window, and the active cell is tracked with `aria-activedescendant` rather than focus. Add a live region for values
changed by other people.

**UX-01, the menus.** `MenuBar.vue` carries `role="menu"` and `role="menuitem"` but has no `aria-haspopup`, no
`aria-expanded`, no `aria-controls`, no arrow-key handling and no focus movement — so the ARIA roles *promise*
keyboard behaviour that does not exist, which is worse for a screen-reader user than plain buttons. Implement the ARIA
menu-button / menubar pattern: focus to the first item on open; Up/Down/Left/Right/Home/End and typeahead; Escape
closes and restores focus; Alt or F10 reaches the bar.

**UX-03, the dialogs.** `Modal.vue` is a plain element with a global Escape listener — no focus trap, no inert
background, no focus restored to the opener. Every dialog uses it. Switching to native `<dialog>` with `showModal()`
gives the trap, the inert background and Escape for free, which makes this the smallest of the four.

**UX-04, contrast — with the numbers.** Measured from `tokens.css` today by the WCAG 2.1 formula:

| Pair | Ratio | Needs |
|---|---|---|
| `--muted` (ink 58%) on white | 4.18:1 | 4.5 |
| `--muted` on mist | 3.85:1 | 4.5 |
| `--rose` as error text on white | 4.17:1 | 4.5 |
| `--teal` as text on white | 3.90:1 | 4.5 |
| `--line` (ink 14%) as a field border on white | 1.33:1 | 3.0 |

`--muted` at **65% ink** clears both grounds (5.24:1 on white, 4.74:1 on mist). `--line` is the interesting one: it
**cannot be fixed by raising the ink percentage**, because 3:1 needs about 50% ink, which is far too heavy for the
decorative dividers that share the token. Split it — keep `--line` for dividers, add `--line-field` at about 50% ink
for input and control boundaries. The design system's own rule already says Rose and Teal are for backgrounds with
white text, not for text on white; the implementation drifted from it.

**Test first,** for all four: add axe to the browser run and have it pass on the workspace page; add a token-contrast
script in `scripts/` that computes every pair and fails below the threshold, so the palette cannot regress silently;
add a Playwright test that opens File, moves with arrows, activates an item and ends with focus on the grid; and one
that checks `document.activeElement` is inside a dialog after opening and back on the opener after closing.

**Done when** the four tests pass and an NVDA/Orca script is in the release checklist. **Dark mode (UX-05) is
separate** and larger: `tokens.css` has zero `prefers-color-scheme` rules and `--surface` is a hard-coded `#ffffff`.

---

### 4 · Get the two measured blockers off the event loop, then decide about the worker pool

**Category:** performance. **Bugs:** PERF-01, PERF-05, PERF-02. **Stories:** E6.3, E3.5. **Size:** the first half is
small — a day or two; the second half is an epic.

The calculation engine is good: incremental, with ranges indexed by 256-row blocks per column, depth-first ordering
with an explicit stack, and cycle detection. One edit in a 50k-row workbook costs about 0.25 ms, against 16.7 ms
before the index. That is not where the problem is.

The problem is that `Connection.handle` is synchronous and runs inside the event-loop coroutine, so **anything slow in
a request stalls every document the server holds.** Two such things were measured today:

| | 1k cells | 10k | 100k | 500k |
|---|---|---|---|---|
| one 64×16 grid window (`cells`) | 0.12 ms | 0.57 ms | 3.64 ms | **21.08 ms** |
| the sheet extent (`sheets`) | 0.06 ms | 0.61 ms | 6.14 ms | **37.97 ms** |

Both are linear in the size of the *sheet*, not the size of the answer. `computes.py::_cells` filters and sorts every
cell in the sheet for each window the grid asks for while scrolling; `_extent` runs two `max()` passes over every
cell, for every sheet, each time `sheets` is called.

**The cheap half, which I would do now.** Maintain the information instead of recomputing it. `Sheet` already tracks a
version per column, so it has the shape for an index: keep rows → sorted columns per sheet, updated by the commands
that set and clear cells, and keep the extent incrementally. Both calls then cost what their answer costs.
*Test first:* guards in `check_debt.py` next to the existing ones — a 64×16 window at 500k cells costs ≤ 2 ms and
within 2× of the cost at 10k; `sheets` at 500k costs ≤ 2 ms.

**The structural half, which needs a decision from you.** PERF-02 is the same shape but cannot be indexed away: every
edit calls `os.fsync` synchronously on the event loop, because durability is promised before the request is
acknowledged. The design already says what to do — a writer task off the loop with group commit, acknowledging after
the batch is synced (D106) — and it was never built. Behind it sits E3.5, the worker pool, which D37 specified and
which does not exist at all: no `multiprocessing`, no process pool, anywhere. Without it, E4.3 (calculating state),
E4.4 (heavy functions), E4.9 (SQL cells) and E3.4's typesetting queue cannot be built, because they all assume
something that can take a second without freezing the server.

**My suggestion:** do the index now, since it is a day and removes the two blockers people will actually hit; and
schedule E3.5 as the next platform epic, before E4.3/E4.4/E4.9, rather than letting each of them discover the same
missing foundation. PERF-07 (a 12 s structure edit at 100k formulas) is real but rarer, and it belongs with E3.5
rather than ahead of it.

---

### 5 · Make the two privacy promises true in the code

**Category:** security. **Bugs:** SEC-05, and the live half of E2.4. **Stories:** E2.4, E2.6. **Size:** medium —
E2.4's live half is small, E2.6 is a week.

The product's central claim is privacy, the website says so, and two specific promises are currently not kept. Both
are known and both have a story; I am raising them because each is a case where **the file is right and the running
system is not**, which is the kind of gap that survives review precisely because the hard part looks done.

**(a) Viewers receive everything while they are connected (E2.4).** `HostedDocument._audience` in `hub.py` filters
only by author (history), by recipient (private chat) and by sender (ephemeral). There is no role check, so a viewer's
socket gets every command, every history entry and every chat message — exactly what D34 says must not happen. The
cryptography already enforces it on the file, which makes the gap easy to miss.
*Fix:* add the role check to `_audience`; a viewer gets state and presence, not the history or chat domains. Keep the
domain names from the container so the two halves use one vocabulary.
*Test first:* a three-client test where an owner, an editor and a viewer are connected; the viewer receives no
`history` and no `chat` event while the other two do. This is small — a day — and closes the live half of E2.4.
The other half (letting a viewer be the first to open a sealed document) needs read-only hosting of the snapshot and
is larger; keep them separate.

**(b) Redaction does not reach the file (SEC-05).** `Document.redact` removes the content from the live state and
from the replayed log. The container has no `redact`: the journal is append-only, packing does not rewrite history,
and the snapshot keeps the old state until the next packing. So a secret typed into a cell and then redacted is still
in the file. It is not reachable on the wire today — there is no `redact` method — which is why it is P2 and not P1,
and it becomes P1 the day redaction is exposed.
*Fix:* the atomic rewrite the design already specifies — on redaction, rewrite the affected blocks and the journal
through the existing temp-file / fsync / rename path, drop the snapshot and rebuild. Note in the help text that copies
and backups made earlier keep the content, because that is true and cannot be fixed.
*Test first:* after `redact`, a byte scan of every file under the document folder finds none of the redacted text.
*Blocked on a decision:* E1.8's redaction contract — what `redacted()` must keep so later commands still replay — is
still open and marked "the owner is thinking about it". It has been open since 2026-11-02 and now blocks two stories.
Settling it is the first step of this item.

---

## Runners-up, not in the five

- **The menu structure (UX-06, UX-09, E5.1).** D4 decided four header-bar menus; the web app has six in a separate
  row; the Linux shell bridges them with a mapping table and a script that clicks the web app's own menus, polling
  every 750 ms to read which items are enabled. That was a deliberate stop-gap and it is well built — but it has to be
  rewritten for every shell, and it is the kind of debt that gets harder as menus grow. **It needs a decision from you
  before it can be fixed:** four menus or six.
- **Internationalization (E5.7, D31).** D31 says i18n is built in *from the start*. There is no gettext, no `.po`, no
  catalogue anywhere — in the packages, the web app or the Linux client. It is the oldest unstarted decision in the
  log and the retrofit cost grows with every screen.
- **`claudia-computes` and `claudia-composes` are still exempt from the API snapshot rule** (E11.5) on the grounds of
  being "proofs". Both are now large, real products with public APIs that other packages import.
- **Coverage is not measured at all** (CODE-01). With ~1,321 Python tests the question is no longer whether tests
  exist but where the gaps are, and there is no way to see.
  *(Measured and held to floors since 2026-11-10, see CODE-01.)*

---

## What is genuinely good, so nobody "fixes" it

- **The kernel's purity test has held through four epics.** `claudia-core` is still standard-library only, still does
  no I/O, and every temptation to put the network, the container or the engine inside it was resisted and recorded.
  That discipline is why the container could be added later without touching the kernel.
- **The typesetting sandbox is the best-tested code in the tree.** Its rules are verified by mutation — weakening
  `-no-shell-escape`, `shell_escape`, `openin_any` or `openout_any` makes six hostile tests fail — and 15
  hostile-input tests run against the real engine. This pattern should be copied to the container and to the AI
  boundary.
- **The container's cryptography is conservative and correct in shape**, and the reader is defended against hostile
  files rather than trusting them.
- **The calculation engine** is incremental, indexed, measured and guarded against regression.
- **The notes record what did not work**, with real negative controls — the worker watchdog disabled and processes
  left behind, the Windows bundle script's silent exit path, XeTeX ignoring fontconfig aliases. That is rarer than it
  should be and worth protecting when notes are edited.
- **The product is honest in the interface** about what is not built yet, which is the right instinct and the opposite
  of what the website currently does (WEB-01).

---

## Method

Cloned `main` at `54d1245`; `uv sync --locked` (Python 3.14.6); ran the full test suite, `scripts/check_debt.py`,
`ruff format --check`, and — after `npm install` and `nuxt prepare` — vitest and `vue-tsc`. Read the gateway, hub,
protocol, computes and composes method tables, the assistant and the AI agent, the container's crypto, container and
journal, the calculation engine, the web menu, modal, grid and token files, the Linux client's manifest and notes, the
CI workflow and the quality gate. Wrote and ran three probes: a scaling benchmark for the grid window and the sheet
extent, a WCAG contrast calculation over the real tokens, and an inspection of the AI's authorisation path. Derived
the status of all 143 backlog stories from the code rather than from the notes, which is how the missing E6.3 work and
the duplicated decision numbers were found.

**Not reviewed:** the website; the Neutralino shell and anything on Windows or macOS (nothing was run there, and the
Windows typesetting sandbox has still never executed); a real language model; the browser e2e scenarios; and
screen-reader behaviour, which was measured by reading and by script rather than by listening.
