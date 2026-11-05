# Claudia — bug tracker

Moved here from the project context on 2026-11-05 (was `qa-bug-tracker.md`). This file is the tracker; the review that
produced the current round is `qa-recommendations.md`. Stories are in `backlog.md` (E-numbers), decisions in
`decision-log.md` (D-numbers).

**Review rounds:** first 2026-11-02 at `f8df891`; second 2026-11-05 at `54d1245` ("E5 desktop clients: linux first
draft"). Statuses below were re-checked against `54d1245` on 2026-11-05 — every item marked *verified open* or *verified
fixed* was re-tested or re-read in that tree, not carried over on trust.

## How to add a bug

Tell the QA role in chat: *title, what you saw, where*. It is entered here with the next ID, a category, a proposed
priority and a status. Every fix follows `CONTRIBUTING.md` rule 1: **the bug first gets a test that fails for the right
reason.** Where an item says "Acceptance", that is the test to write first.

Priorities: **P1** before the product is shown outside the team or runs on any machine other than a trusted laptop.
**P2** before the first release, or before the story it belongs to is called done. **P3** backlog.

Status: `open` · `needs decision` · `in progress` · `fixed` · `wontfix`.
Evidence labels: **measured** (run against the real code), **read** (from reading code, not run), **documented** (a
statement in the docs or on the website).

## Index

| ID | Pri | Category | Title | Status |
|---|---|---|---|---|
| SEC-01 | P1 | Security | DNS rebinding defeats the Origin check | fixed (verified at `54d1245`) |
| SEC-02 | P2 | Security | Anyone who reaches the server can create unlimited documents | fixed (verified at `54d1245`) |
| SEC-03 | P2 | Security / Perf | Password hashing runs on the event loop | fixed (verified at `54d1245`) |
| SEC-04 | P2 | Security | Answer time reveals whether a document exists | fixed (verified at `54d1245`) |
| SEC-05 | P2 | Security | Redaction leaves the content in the journal and in packed blocks | verified open |
| SEC-06 | P2 | Security | The server's self-signed certificate is a CA with no name constraints | verified open |
| SEC-07 | P2 | Security | Plain-text passwords allowed on non-loopback addresses | fixed (verified at `54d1245`) |
| SEC-08 | P3 | Security | `npm audit` / `pip-audit` are not run by the gate or CI | verified open |
| SEC-09 | P3 | Security | User names can be confusable (homoglyphs) | open (unverified) |
| SEC-10 | P2 | Security / Arch | The AI's method allow-list is enforced in the model parser, not at dispatch | **new, verified open** |
| SEC-11 | P3 | Security | No per-address back-off on failed logins | verified open |
| PERF-01 | P2 | Performance | `cells` window cost grows with the whole sheet | verified open (re-measured) |
| PERF-02 | P2 | Performance | Journal `fsync` on the event loop for every edit | verified open |
| PERF-03 | P3 | Performance | `users.json` rewritten and fsynced in full on every user added | superseded by the container |
| PERF-04 | P3 | Performance | `GET /api/docs` scans the disk on every request | fixed (listing cache) |
| PERF-05 | P2 | Performance | `sheets` recomputes the extent by scanning every cell | **new, verified open** |
| PERF-06 | P3 | Performance | Packing rewrites the whole zip; threshold packing on the event loop | verified open |
| PERF-07 | P3 | Performance | Structure edits recalculate the whole workbook (~12 s at 100k formulas) | verified open |
| UX-01 | P2 | UX | Menus cannot be operated with the keyboard | verified open |
| UX-02 | P2 | UX | The grid has no accessible structure | verified open |
| UX-03 | P2 | UX | Dialogs do not manage focus | verified open |
| UX-04 | P2 | UX | Text and border colours fail WCAG contrast | verified open (re-measured) |
| UX-05 | P3 | UX | No dark mode | verified open |
| UX-06 | — | UX | Web menu differs from decisions D4/D5 | needs decision |
| UX-07 | P2 | UX / Web | Website blocks pinch-zoom (`user-scalable=no`) | open (not re-checked) |
| UX-08 | P3 | UX | Open and Create sit side by side; a typo cannot be told from a wrong password | open |
| UX-09 | P2 | UX | Six web menus against four in D4; the Linux shell maps between them | **new** |
| PROC-01 | P1 | Process | No CI workflow in the repository | fixed (verified at `54d1245`) |
| PROC-02 | P2 | Process | The quality gate prints "everything is clean" when half of it was skipped | verified open (re-measured) |
| PROC-03 | P2 | Process | Work described as delivered is not in the repository | **new, verified open** |
| CODE-01 | P2 | Code | No coverage, no web lint; Playwright not declared | verified open |
| CODE-02 | P3 | Code | 26 build files tracked in `web/dist` | verified open |
| CODE-03 | P3 | Code | README is out of date | open (not re-checked) |
| CODE-04 | P3 | Code | Untyped functions escape the type check | verified open |
| CODE-05 | P3 | Code | Dead branch in `Gateway.admit`; stale docstring in `state.py` | verified open |
| CODE-06 | P3 | Code | `--max-connections` is per document, not per server | open |
| CODE-07 | P3 | Code | `uv.lock.rej` committed at the repository root | **new, verified open** |
| CODE-08 | P3 | Code | `ruff format --check` fails; the gate does not run it | **new, verified open** |
| CODE-09 | P3 | Code | e2e scripts exist without `package.json` entries | **new, verified open** |
| DOC-01 | P2 | Docs | Decision numbers D70–D82 and D97–D99 are used twice for different decisions | **new, verified open** |
| WEB-01 | P1 | Website | The website describes features the product does not have | needs decision |
| WEB-02 | P3 | Website | Download buttons are `#` placeholders | open |

---

## Security

### SEC-01 · DNS rebinding defeats the Origin check · P1 · fixed
Fixed in claudia-server 0.6.0: `HostGuard` (`hosts.py`) as the outermost ASGI layer, a Host allow-list, 403 / close
4403, `--allow-host`. Verified at `54d1245`: `app.py` adds `HostGuard` last so it sees a request first, and
`test_server_hosts.py` covers it. Details: `notes/e3-server-and-security.md`.

### SEC-02 · Anyone who reaches the server can create unlimited documents · P2 · fixed
Fixed in 0.6.0: `--max-documents` (1000), `--max-waiting` (256), `--max-waiting-per-address` (64), optional access
secret. Verified at `54d1245`: `_Waiting` in `app.py`, `hub.ensure_room()`, `Gateway.accepts_secret`.

### SEC-03 · Password hashing runs on the event loop · P2 · fixed
Verified at `54d1245`: `Gateway._verify` runs `directory.verify` through `asyncio.to_thread` behind a
`max_hashing` semaphore. Note the interaction found while building the container: OpenSSL's multi-lane Argon2id is
serialised by a process-wide lock, so the effective concurrency is 1 at the default parameters. That is a throughput
limit (2.5–5 logins per second), not a correctness problem, and it is the reason the KDF calibration question matters.

### SEC-04 · Answer time reveals whether a document exists · P2 · fixed
Verified at `54d1245`: `Gateway._admit` runs the same `_verify` on the not-found path before refusing. The guarding
test is a timing comparison and is known to be flaky on a loaded machine; see PROC note in CODE-01.

### SEC-05 · Redaction leaves the content in the journal and in packed blocks · P2 · verified open
**Evidence (read, `54d1245`).** `claudia_container.container` has no `redact`. The journal is append-only and packing
writes blocks; neither rewrites history to remove a redacted command. The kernel's `Document.redact` changes the live
state and the log it replays, but the bytes stay in the file.
**Why it matters.** Redaction is a stated product promise (D21, E1.8 "done (draft)") and the container is now the real
store, so this is no longer only about a demo journal. Not reachable on the wire today (no `redact` method), so P2; it
becomes P1 the day redaction is exposed or the website's privacy claim (WEB-01) is kept.
**Fix.** The atomic rewrite named in the E2 design: on redaction rewrite the affected blocks and the journal (temp
file, fsync, rename, directory fsync), drop the snapshot, rebuild. Also state plainly in the help text that copies and
backups made earlier keep the content.
**Acceptance.** After `redact`, a byte scan of every file under the document folder finds none of the redacted text.

### SEC-06 · The server's self-signed certificate is a CA with no name constraints · P2 · verified open
**Evidence (read, `54d1245`).** `certs.py` line 100: `BasicConstraints(ca=True, path_length=0)`, critical, with
`key_cert_sign=True`. The private key sits on the server's disk.
**Why it matters.** If a person installs it into the system trust store (which "trust this certificate" instructions
invite), whoever steals the key file can sign certificates for *any* site for that person.
**Fix.** Prefer `ca=False` plus partial-chain verification in `claudia_client/trust.py`, or add a critical
`NameConstraints` extension limited to the certificate's own names.
**Acceptance.** The client still connects with fingerprint pinning; `openssl verify` of a certificate for another name
signed by the same key fails.

### SEC-07 · Plain-text passwords on non-loopback addresses · P2 · fixed
Verified at `54d1245`: `--no-tls` with a non-loopback `--host` raises `UsageError` unless `--behind-proxy`.

### SEC-08 · Dependency audits are not run by the gate or CI · P3 · verified open
**Evidence (read, `54d1245`).** `scripts/check_debt.py` runs ruff, mypy, vulture, pytest, Sphinx, perf guards and the
web checks. It runs no `npm audit`, no `pip-audit`. `.github/workflows/ci.yml` adds none either.
**Fix.** Add `npm audit --omit=dev` and `pip-audit` (or `uv pip audit`) to the gate, with an allow-list that needs a
written reason per entry.
**Acceptance.** The gate fails on a new high or critical advisory.

### SEC-09 · User names can be confusable · P3 · unverified
**Evidence (read).** `claudia_container.crypto._normalise_name` uses NFKC and `casefold`, which does not fold Cyrillic
`а` to Latin `a`. Only an owner adds users, so the risk is an owner impersonating a colleague in the history.
**Fix.** Reject mixed-script names, or mark two confusable names in one document. Verify with a two-user test first.

### SEC-10 · The AI's method allow-list is enforced in the model parser, not at dispatch · P2 · new, verified open
**Evidence (measured, `54d1245`).**
- `apps.MODEL_METHODS` is `{"computes": ("set_cells", "add_sheet", "structure")}`. It decides which `ToolSpec`s are
  *described to the model in the prompt*.
- `claudia_ai.agent.Agent._take_calls` drops a request whose name is not in that set. This is a filter on the model's
  generated text, inside the AI library.
- `Assistant._call` (`assistant.py`) calls `hosted.methods.dispatch(context, method, params)` with **no allow-list**. A
  check for `MODEL_METHODS` in its source: absent.
- `protocol.py` contains **zero** `account.system` checks. The generic write method `apply` decodes any command and
  executes it as the calling account.
- `composes.py` has two `account.system` checks (`_people_only` guards `replace_text` and `set_style`; `suggest` is
  assistant-only) — but `apply` is inherited from `core_methods` and bypasses both.
- Write methods reachable at dispatch that the model is never offered: core `apply`, `chat`, `lock`, `redo`,
  `save_checkpoint`, `undo`, `unlock`; composes adds `replace_text`, `set_style`, `accept_suggestion`, and the style
  methods. `MODEL_METHODS` has no entry for composes at all, so a composes assistant is offered nothing — and is
  stopped only because `Agent` finds an empty allowed set.
**Why it matters.** Two product rules depend on this boundary: D63 ("edits by the AI are suggestions; people write")
and E7.6 ("a guarantee that the AI cannot add functions"). Both are currently enforced by a regex-extracted JSON block
filtered against a name set in a client library, not by the server's authorisation layer where the account is known.
Today nothing is remotely exploitable: every engine in the tree is trusted in-process code. It becomes serious at two
named milestones — E7.5, which puts document content into the prompt (prompt injection from a cell then chooses method
names), and E3.6/D8, which moves the engine to another machine behind a socket.
**Fix.** Move the allow-list to the authorisation layer: give `Account` (or the `Context`) the set of methods it may
call, and check it in `MethodTable.dispatch` before the method runs, so every path — `Assistant._call`, a future remote
AI connection, and the wire — passes the same gate. Add `account.system` to the generic `apply` so the assistant cannot
reach a command whose wrapper method would refuse it. Give composes an explicit `MODEL_METHODS` entry (`suggest` only).
**Acceptance.** A test builds an `Assistant` whose engine returns `Call("apply", …)` and `Call("chat", …)` and shows
both are refused with `forbidden` and change nothing; a test shows the assistant cannot reach `replace_text` through
`apply`; a test shows a composes assistant may call `suggest` and nothing else.

### SEC-11 · No per-address back-off on failed logins · P3 · verified open
**Evidence (read).** `_Waiting` bounds how many connections wait to be let in, but nothing slows a patient guesser who
logs in once, fails, disconnects and repeats. Named as the remaining part of E2.7 in the security-fix notes.
**Fix.** Per-address and per-(document, name) back-off with a cap, on top of the hashing semaphore.

---

## Performance

### PERF-01 · `cells` window cost grows with the whole sheet · P2 · verified open (re-measured)
**Evidence (measured, `54d1245`).** `claudia_server/computes.py` `_cells` line 82 is
`sorted((r, c) for r, c in found.cells if …)`: it scans every cell of the sheet and sorts the matches. Measured on this
machine for one 64×16 window:

| cells in the sheet | window | growth vs 1k |
|---|---|---|
| 1,000 | 0.12 ms | ×1 |
| 10,000 | 0.57 ms | ×5 |
| 100,000 | 3.64 ms | ×30 |
| 500,000 | 21.08 ms | ×172 |

Linear in the size of the sheet, not in the size of the window. The grid asks for such a window on every scroll, and
`Connection.handle` runs synchronously on the event loop, so the whole server pauses for it.
**Fix.** Keep an index per sheet (rows → sorted columns) in `claudia-computes`, maintained by the commands; or cache
chunks per revision.
**Acceptance.** A guard in `scripts/check_debt.py`: window cost at 500k cells ≤ 2 ms and within 2× of the cost at 10k.

### PERF-02 · Journal `fsync` on the event loop for every edit · P2 · verified open
**Evidence (read, `54d1245`).** `claudia_container/journal.py` `append` does `flush()` then `os.fsync()`
synchronously (lines 210–211); `filestore.py` `_write` does the same for the plain store. The call path is
`_Live.run` → `connection.handle` (synchronous) → `methods.dispatch` → `document.execute` → store append. So every
keystroke-sized edit fsyncs on the event loop and stalls every document the server holds.
**Fix.** The group commit named in the E2 design (D76 of that document, renumbered D106 here): a writer task off the
loop, several records per fsync, the request acknowledged after its batch is synced. Measure first on a spinning disk
and on a network volume.
**Acceptance.** With a store whose `append` sleeps 50 ms, `ping` latency of other users stays under 20 ms.

### PERF-03 · `users.json` rewritten in full on every user added · P3 · superseded
The sealed container replaced `FileDirectory` for `--dir`; people live in `people.bin` inside the document. Keep the
item only for `--plain-dir`, which is the legacy store.

### PERF-04 · `GET /api/docs` scans the disk on every request · P3 · fixed
The server keeps a listing cache built from the manifests (E2 slice 3).

### PERF-05 · `sheets` recomputes the extent by scanning every cell · P2 · new, verified open
**Evidence (measured, `54d1245`).** `computes.py` `_extent` runs two `max()` passes over `sheet.cells` for every sheet,
and `_sheets` calls it for each. Measured: 0.06 ms at 1k cells, 6.14 ms at 100k, **37.97 ms at 500k** — worse than
PERF-01 and on the same event loop. The client calls `sheets` on open and after structure changes.
**Fix.** Maintain the extent incrementally in `Sheet` as cells are set and cleared (it already tracks a version per
column), or cache it per revision.
**Acceptance.** A guard: `sheets` on a 500k-cell workbook costs ≤ 2 ms.

### PERF-06 · Packing rewrites the whole zip; threshold packing on the event loop · P3 · verified open
**Evidence (documented, E2 slice 3 notes).** Packing writes the whole zip again every 500 changes and at release.
Release runs in a thread; threshold packing does not. Fine up to some tens of megabytes; larger documents need
appending or a split.

### PERF-07 · Structure edits recalculate the whole workbook · P3 · verified open
**Evidence (documented, formula notes).** Inserting a row in a workbook of 100k formulas takes about 12 s: every
formula is rewritten and recalculated. Ordinary edits are incremental and fast (~0.25 ms in a 50k-row workbook).
**Fix.** Rewrite only formulas that refer to the edited sheet; move cells without recompiling.

---

## UX and UI

### UX-01 · Menus cannot be operated with the keyboard · P2 · verified open
**Evidence (read, `54d1245`).** `web/app/components/MenuBar.vue` still carries `role="menu"` and `role="menuitem"` but
has no `aria-haspopup`, no `aria-expanded`, no `aria-controls`, no arrow-key handling and no focus movement into the
open menu. The only keyboard listener is a global Escape. The ARIA roles promise arrow-key behaviour that does not
exist, which is worse for a screen-reader user than plain buttons would be.
**Fix.** Implement the ARIA menu-button / menubar pattern: `aria-haspopup`, `aria-expanded`, `aria-controls`; focus to
the first item on open; Up/Down/Left/Right/Home/End/typeahead; Escape closes and restores focus; Alt or F10 reaches the
bar.
**Acceptance.** A browser test opens File, moves with arrows, activates an item, and ends with focus back on the grid.

### UX-02 · The grid has no accessible structure · P2 · verified open
**Evidence (read, `54d1245`).** `SheetGrid.vue` has exactly two ARIA attributes: `role="grid"` and
`aria-label="table"` (plus `aria-label="editing cell"` on the editor). No `role="row"`, no `role="gridcell"`, no
`aria-rowcount`/`aria-colcount`, no `aria-rowindex`/`aria-colindex`, no `aria-activedescendant`, no `aria-selected`. A
screen reader cannot say what is in a cell or where it is.
**Why it matters.** D69 names public administration and schools as audiences. In the EU those buyers usually have to
meet WCAG 2.1 AA through EN 301 549 (in Germany BITV 2.0). This is the single biggest gap against that bar, and the
grid is the product.
**Fix.** For the virtualised grid: `aria-rowcount`/`aria-colcount` for the whole sheet, `aria-rowindex`/`aria-colindex`
on rendered rows and cells, `role=row`/`gridcell`/`columnheader`/`rowheader`, `aria-activedescendant` for the active
cell, and a live region for values changed by other people.
**Acceptance.** axe in the browser run passes on the workspace page; an NVDA/Orca script joins the release checklist
(E5.10).

### UX-03 · Dialogs do not manage focus · P2 · verified open
**Evidence (read, `54d1245`).** `Modal.vue` is a plain element with a global `keydown` listener for Escape. No
`<dialog>`, no `showModal()`, no focus trap, no `inert` on the background, no focus restored to the opener. Every
dialog in the app uses it (Share, Prompt, Help, Styles, Recovery key).
**Fix.** Use native `<dialog>` with `showModal()`, which gives the trap, the inert background and Escape for free;
move focus to the first field; restore focus to the opening control on close.
**Acceptance.** After open, `document.activeElement` is inside the dialog; Tab cycles inside it; after close focus is
on the control that opened it.

### UX-04 · Text and border colours fail WCAG contrast · P2 · verified open (re-measured)
**Evidence (measured from `web/app/assets/tokens.css` at `54d1245`.)** Ratios computed by the WCAG 2.1 formula, with
`color-mix(… transparent)` treated as alpha compositing over the stated background:

| Pair | Ratio | Needs | |
|---|---|---|---|
| `--muted` (ink 58%) on `--surface` white | 4.18:1 | 4.5 | fail |
| `--muted` on `--paper` | 4.05:1 | 4.5 | fail |
| `--muted` on `--mist` | 3.85:1 | 4.5 | fail |
| `--rose` as error text on white | 4.17:1 | 4.5 | fail |
| `--teal` as text on white | 3.90:1 | 4.5 | fail |
| `--apricot` as text on white | 2.11:1 | 4.5 | fail |
| `--line` (ink 14%) as a field border on white | 1.33:1 | 3.0 | fail |
| `--line` on paper | 1.32:1 | 3.0 | fail |
| `--ink` body text on paper | 15.14:1 | 4.5 | pass |
| white on `--iris` | 6.46:1 | 4.5 | pass |
| `--iris` text on paper | 5.84:1 | 4.5 | pass |

**Fix, with the numbers.** `--muted` at **65% ink** clears both grounds (5.24:1 on white, 4.74:1 on mist); 70% gives
more room. The error rose and the teal text variant need darker values. `--line` **cannot be fixed by raising the ink
percentage alone** for its use on form fields: 40% ink still only reaches 2.48:1, and 3:1 needs about **50% ink**,
which is far too heavy for the decorative dividers that also use the token. Split it: keep `--line` for dividers and
add a `--line-field` at about 50% ink for input and control boundaries. The dark history panel was not measured here.
**Acceptance.** A token test (a script in `scripts/`) computes every pair and fails below the thresholds, so the
palette cannot regress silently.

### UX-05 · No dark mode · P3 · verified open
**Evidence (measured).** `web/app/assets/tokens.css` contains **zero** `prefers-color-scheme` rules, and `--surface` is
a hard-coded `#ffffff`. E0.3 lists a dark/light switch as an acceptance criterion and GNOME apps follow the system
setting. (The server's own fallback landing page in `app.py` does implement dark mode, which makes the gap visible.)
**Fix.** Define dark values for every token, follow the system setting, and let the shell contract pass the OS value.

### UX-06 · Web menu differs from decisions D4/D5 · needs decision
D4 says four header-bar menu buttons: File, Edit, Tools, Help. The web app has six menus (File, Edit, Format, View,
Tools, Help) in a separate menu-bar row, and the File items read *New sheet…, Save, Save with a name…, Share…, Close
document* rather than *Open, Save, Save As, Exit*. See also UX-09, which is the consequence.
**Decision needed.** Either record the six-menu structure as the decision and update D4/E5.1, or fold the menus back
into the four and align the labels.

### UX-07 · Website blocks pinch-zoom · P2 · open
`user-scalable=no` in the viewport meta of the home page (WCAG 1.4.4 / 1.4.10). Not re-checked in this round; the
website was out of scope.

### UX-08 · Open and Create sit side by side · P3 · open
A mistyped document name on *Open* gives "the name or password is not right (or there is no such document)", and one
click on *Create document* then makes the person owner of a new empty document.
**Fix.** While the server lists documents, say when the typed name is not in the list; mark the default button by
context; make placeholders visibly lighter than entered text.

### UX-09 · Six web menus against four in D4; the Linux shell maps between them · P2 · new
**Evidence (read, `54d1245`).** The Linux shell carries a mapping table (`manifest.py` plus `data/webroutes.json`) and
a page adapter (`data/shim.js`) that *clicks the web app's own menus as a person would* to carry out a native menu
action, polling every 750 ms to read which items are enabled or ticked. This was a deliberate stop-gap (the owner asked
that the web app not be changed), and a drift-guard test fails when a web label a route uses is renamed.
**Why it matters.** It is a DOM click-path between two menu structures that D4 and E5.1 say should be one manifest. It
is fragile by construction, it costs a poll every 750 ms, and it has to be rewritten for every shell. The cost grows
with each app and each new menu item.
**Fix.** E5.1 as written: one menu and action manifest that generates the GMenu XML, the Neutralino menu and the web
menu, and the web app implementing the shell contract directly. Then `shim.js` and `webroutes.json` are deleted.
Settling UX-06 is a precondition.

---

## Process and code

### PROC-01 · No CI workflow in the repository · P1 · fixed
`.github/workflows/ci.yml` exists at `54d1245`: a Python matrix over ubuntu, windows and macos running
`scripts/check_debt.py`, a web job (`npm ci`, `nuxt prepare`, `vitest`, `vue-tsc`), a Monday schedule and
`workflow_dispatch`. Whether it has ever run green on Windows and macOS is still unknown from the tree alone.

### PROC-02 · The quality gate prints "everything is clean" when half of it was skipped · P2 · verified open (re-measured)
**Evidence (measured, `54d1245`).** Run in a fresh clone without `npm install`:

```
-- ruff: ok      -- mypy: ok       -- vulture: ok    -- tests: ok      -- docs: ok
-- perf claudia-core: ok           -- perf claudia-computes: ok
-- web tests: skipped (run `npm install` in web/ first)
-- web types: skipped (run `npm install` in web/ first)
-- mypy linux client: ok           -- linux client tests: ok

Technical debt check: everything is clean.      [exit 0]
```

**Why it matters more than it looks.** `scripts/check_debt.py` has no `--ci` flag, and `.github/workflows/ci.yml` calls
it with no arguments. The Python job never runs `npm install`, so **in CI the web checks are skipped on all three
operating systems and the gate still reports clean and exits 0.** The separate `web` job does run vitest and `vue-tsc`
on ubuntu, so the checks are not lost — but the gate's own verdict is untrue, and the Linux-client tests skip the same
way wherever `/usr/bin/python3` lacks pytest and jsonschema.
**Fix.** Print "clean except skipped: …" and add `--ci`, which turns a skip into a failure; CI always passes `--ci`,
with the genuinely platform-specific skips listed explicitly.
**Acceptance.** With no `node_modules`, `check_debt.py --ci` exits non-zero.

### PROC-03 · Work described as delivered is not in the repository · P2 · new, verified open
**Evidence (measured, `54d1245`).** `e4-e6-formulas-notes.md` describes point-and-click cell references for E6.3 as
built on 2026-11-03: `web/app/lib/pointing.ts`, `web/tests/pointing.test.ts` with 22 cases, `REFERENCE_COLORS`,
`slotAt`, and a nine-case browser scenario `npm run e2e:pointing`. None of it exists:

```
ls web/app/lib/pointing.ts          -> No such file
git log --all -- web/app/lib/pointing.ts -> no commits, on any branch
grep -rl "REFERENCE_COLORS\|slotAt" web/ -> nothing
grep "e2e:pointing" web/package.json -> nothing
```

**Why it matters.** The delivery model is "Claude produces a patch, the owner creates the branch and commits". A patch
can be lost in that gap without anybody noticing, and the notes then record a feature as done that nobody can use. It
also makes the notes an unreliable basis for deciding what to build next — which is exactly what they are for. This
one was caught only because the status of every backlog item was re-derived from the code in this round.
**Fix.** Two parts. (1) Recover or rebuild the E6.3 pointing work. (2) Close the gap: a note may only say "built" with
the commit that carries it, and the backlog status is derived from the code, never from a note. A cheap check is a line
in the gate that greps the notes for file paths that do not exist.
**Acceptance.** The claim is either true in the tree or corrected in the note, and `backlog.md` shows E6.3 without
click-to-insert.

### CODE-01 · No coverage, no web lint; Playwright not declared · P2 · verified open
**Evidence (read, `54d1245`).** No `pytest-cov` or coverage settings in `pyproject.toml`; no eslint, prettier or Biome
in `web/package.json`; the `e2e` scripts run `node e2e/*.cjs`, which needs Playwright, and Playwright is not in
`devDependencies`.
**Why it matters.** `CONTRIBUTING.md` promises TDD. Without a coverage number and a trend there is nothing to check
that promise against — and the test suite is large enough (≈1,321 Python tests, 195 web tests) that the question is
now about where the gaps are, not whether tests exist.
**Fix.** `pytest-cov` with a floor per package, starting at the measured value and ratcheting up; a linter for `web/`;
declare Playwright.

### CODE-02 · 26 build files tracked in `web/dist` · P3 · verified open
**Evidence (measured).** `git ls-files web/dist` returns 26 files. `.gitignore` names `web/.nuxt` and `web/.output` but
not `web/dist`, and `docs/web.md` builds to `web/.output/public`, so `web/dist` is stale output.
**Fix.** `git rm -r --cached web/dist` and add it to `.gitignore`.

### CODE-03 · README is out of date · P3 · open
Not re-checked in this round.

### CODE-04 · Untyped functions escape the type check · P3 · verified open
**Evidence (read).** `pyproject.toml` sets `check_untyped_defs = true` but not `disallow_untyped_defs`, so a function
with no annotations is not checked against its signature — for example `SinglePageApp.get_response(self, path, scope)`
and `Gateway._hello` in `app.py`.
**Fix.** Turn on `disallow_untyped_defs` for `claudia_core` first (nearly typed already), then package by package with
per-module overrides.

### CODE-05 · Dead branch in `Gateway.admit`; stale docstring in `state.py` · P3 · verified open
**Evidence (read, `54d1245`).** `app.py` lines 232–235 still hold the branch commented "(cannot happen; keeps verify's
checks)".
**Fix.** Remove the branch with its test, or replace the comment with an assertion that states the invariant.

### CODE-06 · `--max-connections` is per document, not per server · P3 · open
Rename to `--max-connections-per-document`, document it, and keep the server-wide caps from SEC-02 separate.

### CODE-07 · `uv.lock.rej` committed at the repository root · P3 · new, verified open
**Evidence (measured).** `uv.lock.rej` is tracked at the root: rejected hunks from a failed `git apply` of a lock-file
update. It shows two things that did not land: `claudia-creates` as a dependency of `claudia-server`, and a
`cryptography` floor moving between `>=43` and `>=44`.
**Why it matters.** CI runs `uv sync --locked`, so a lock file that disagrees with the package metadata fails the build
for everyone. The `cryptography` floor is not cosmetic: Argon2id first appears in `cryptography` 44, and the container
depends on it, so a `>=43` floor allows an install that cannot open a document.
**Fix.** Delete the file; regenerate the lock with `uv lock`; confirm the `cryptography` floor is `>=44` wherever it is
declared.
**Acceptance.** `uv sync --locked` succeeds from a fresh clone; `git ls-files '*.rej' '*.orig'` is empty; a gate line
fails the build if a `.rej` or `.orig` file is ever tracked.

### CODE-08 · `ruff format --check` fails; the gate does not run it · P3 · new, verified open
**Evidence (measured, `54d1245`).** `uv run ruff format --check .` reports **1 file would be reformatted**
(`docs/conf.py`). `scripts/check_debt.py` runs `ruff check` but never `ruff format --check`, so the repository has no
enforced format and the drift is invisible.
**Fix.** Format the file and add `ruff format --check .` to the gate as its own check.

### CODE-09 · e2e scripts exist without `package.json` entries · P3 · new, verified open
**Evidence (measured).** `web/e2e/` holds `composes.cjs`, `demo.cjs`, `recovery.cjs`, `resilience.cjs`, `slides.cjs`
and `styling.cjs`. `web/package.json` has scripts for only four of them: `e2e`, `e2e:composes`, `e2e:slides`,
`e2e:resilience`. `styling.cjs` and `recovery.cjs` — the scenarios for the two newest features — can only be run by
typing the path.
**Fix.** Add `e2e:styling` and `e2e:recovery`, or one `e2e:all`; and a test that every file in `e2e/` has a script.

### DOC-01 · Decision numbers are used twice for different decisions · P2 · new, verified open
**Evidence (measured, project context and `54d1245`).** Two blocks of decision numbers were allocated twice:

| Number | Meaning in `decision-log.md` | Meaning in the E2 / Linux-client notes |
|---|---|---|
| D70 | OpenDocument is the first interchange family | Threat model |
| D71 | Goal, audience and stage are suggestions | Key hierarchy |
| D72 | Material moves between apps through the client | User names are not visible |
| D73 | Styling is CSS in all three apps | Readable without a password |
| D74 | Cut, Copy, Paste in the Edit menu | Primitives: Argon2id, AES-256-GCM |
| D75 | Details of styling | Recovery key |
| D76 | Help system is a knowledge base | Write path (journal, group commit) |
| D77–D82 | creates first draft (shapes, styles, ids, locks) | container package, export, password rules, downloads, names, extension |
| D97–D99 | Windows sandbox, user's own LaTeX, help topic | Layout of native clients, shell contract versioning, local server |

The collision is **live in the source**, not only in documents: `claudia_container/crypto.py` cites D72, D73 and D74
meaning hidden names, the plain manifest and the primitives, while `claudia_server/composes.py` cites D73 and D75
meaning styling-is-CSS and the styling details. The same number means two things two directories apart.
**Why it matters.** The decision log is the project's memory and the thing stories are justified against. A reader who
follows a D-number from a docstring can land on the wrong decision, and any future "this rests on D73" is ambiguous.
**Fix.** Done for the documents in this round: `decision-log.md` keeps the product numbering (it was first and is cited
most widely), the E2 block moves to **D100–D112** and the native-client block to **D113–D119**, with a mapping table in
the log so old references resolve. What remains is the code: update the D-number citations in `claudia-container`,
`claudia-server` and `claudia-creates` to the new numbers.
**Acceptance.** Every `D<number>` in the source resolves to exactly one entry in `decision-log.md`; a gate line checks
it.

---

## Website

### WEB-01 · The website describes features the product does not have · P1 · needs decision
From the first round, and worth re-checking now that more is true: encryption, formulas and a Linux client now exist,
so several of the claims have caught up. Import and export of Word, Excel, PowerPoint and OpenDocument files still do
not exist in any form (no code under `packages/*/src` touches those formats), and "run in a European cloud" has no
images or deployment behind it.
**Decision needed.** Either mark each item *planned*, or soften the wording until it is true. The honest "what works
today" block proposed in the first round would now be a strong one: live co-editing, history, presence, per-document
passwords and encryption at rest, recovery keys, formulas, styles, three apps, a Linux client.

### WEB-02 · Download buttons are `#` placeholders · P3 · open

---

## Verified positives (so nobody "fixes" them)

- The Python gate is genuinely green at `54d1245` on Python 3.14.6: ruff, mypy, vulture, **≈1,321 tests** (8 skipped,
  the Windows-only sandbox ones), Sphinx with warnings as errors, both performance guard suites, and the Linux client's
  own mypy and tests. Web: **195 vitest tests** in 14 files, `vue-tsc` clean.
- The container's cryptography is conservative and correct in shape: Argon2id with bounded parameters read from an
  untrusted file, HKDF with distinct labels per purpose, AES-256-GCM with a fresh random nonce and additional
  authenticated data naming document, domain and position, and a hash chain plus head record that detects a changed,
  swapped, moved or truncated block. Known-answer tests come from RFC 5869, RFC 9106 and the GCM vectors.
- The container reader defends against hostile files: entry count, entry size, total size, compression ratio, name
  pattern, no absolute paths or `..`, never extracting to disk.
- The typesetting sandbox is defended in depth and the defences are *mutation-tested*: weakening `-no-shell-escape`,
  `shell_escape`, `openin_any` or `openout_any` makes six hostile tests fail. 15 hostile-input tests run against the
  real engine.
- The formula engine is incremental and well-indexed: a dependency index with ranges filed by 256-row blocks per
  column, depth-first ordering with an explicit stack (so a 20k-deep chain is fine), cycle detection to `#CIRC!`, and
  `math.fsum` so sparse iteration order cannot change a sum.
- `PEP 758` syntax (`except A, B:`) is used deliberately and is valid on the project's Python 3.14; any tool that
  parses the tree needs 3.14.
- Credentials travel in the first WebSocket frame, never in a URL; the name `ai` is protected Unicode-aware; message
  size, text length, region count and `set_cells` size are limited; slow clients are dropped rather than buffered.

## Not reviewed (and why)

The website (out of scope this round); the Neutralino shell (does not exist); a real language model (no model could be
downloaded); Windows and macOS (nothing was run there, and the Windows sandbox layer has still never executed); the
browser e2e scenarios (not run here); screen-reader behaviour (UX-01/02/03 are measured by reading and by script, not
by listening); the history panel's contrast on its dark background; ODF and OOXML (no code exists).

## Method, this round

Cloned `main` at `54d1245`, synced the environment with `uv sync --locked` (Python 3.14.6), ran the full test suite,
ran `scripts/check_debt.py`, installed the web packages and ran vitest and `vue-tsc`, and ran `ruff format --check`.
Read the server's gateway, hub, protocol, computes and composes method tables, the assistant and AI agent, the
container's crypto, container and journal, the calculation engine, the web menu, modal, grid and token files, the
Linux client's notes and manifest, the CI workflow and the quality gate. Wrote and ran three probes: a scaling
benchmark for the grid window and the sheet extent, a WCAG contrast calculation over the real tokens, and an
inspection of the AI's authorisation path. Cross-checked every claim in the implementation notes that asserted a file
or feature exists.
