# Claudia — bug tracker

Moved here from the project context on 2026-11-05 (was `qa-bug-tracker.md`). This file is the tracker; the review that
produced the current round is `qa-recommendations.md`. Stories are in `Projects/claudia-office/_tasks/` (E-numbers), decisions in
`decision-log/` (D-numbers).

**Review rounds:** first 2026-11-02 at `f8df891`; second 2026-11-05 at `54d1245` ("E5 desktop clients: linux first
draft"). Statuses below were re-checked against `54d1245` on 2026-11-05 — every item marked *verified open* or *verified
fixed* was re-tested or re-read in that tree, not carried over on trust. Fourth round 2026-11-12 at `7e619a2` (all
feature branches merged): new items UX-20 to UX-23, SEC-12 to SEC-17, PERF-08, PROC-09 to PROC-16, CODE-13 to CODE-15 (and in the follow-up on `e56e8f9`: UX-24 to UX-27, PROC-17, CODE-16);
the statuses of SEC-11, PERF-01, PERF-02, PERF-05 and UX-01 to UX-05 were re-checked in that tree
(`qa-recommendations.md`).

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
| SEC-08 | P3 | Security | `npm audit` / `pip-audit` are not run by the gate or CI | npm fixed 2026-11-11; `pip-audit` open |
| SEC-09 | P3 | Security | User names can be confusable (homoglyphs) | open (unverified) |
| SEC-10 | P2 | Security / Arch | The AI's method allow-list is enforced in the model parser, not at dispatch | fixed 2026-11-06 |
| SEC-11 | P3 | Security | No per-address back-off on failed logins (now also the admin sign-in) | verified open (2026-11-12) |
| SEC-12 | **P1** | Security | Anyone who reaches an exposed server with no administrator can become its administrator | **new, open** |
| SEC-13 | P2 | Security | The web app is served without CSP, frame-ancestors, nosniff or referrer headers | **fixed** 2026-11-12 |
| SEC-14 | P3 | Security / Privacy | `/api/swagger` loads its script from a CDN; the API description is public | **new, open** |
| SEC-15 | P2 | Security | Office import reads every zip part whole and parses some XML with default parsers | **new, open** (P1 once import is on the wire) |
| SEC-16 | P3 | Security | The LaTeX program setting accepts any executable on the server | **new, open** |
| SEC-17 | P2 | Security | A viewer's connection receives the whole history and chat (E2.4), which the file itself withholds | open since 2026-11-05, **now tracked** |
| PERF-01 | P2 | Performance | `cells` window cost grows with the whole sheet | **fixed** (re-measured 2026-11-12) |
| PERF-02 | P2 | Performance | Journal `fsync` on the event loop for every edit | verified open (2026-11-12; see CODE-13) |
| PERF-03 | P3 | Performance | `users.json` rewritten and fsynced in full on every user added | superseded by the container |
| PERF-04 | P3 | Performance | `GET /api/docs` scans the disk on every request | fixed (listing cache) |
| PERF-05 | P2 | Performance | `sheets` recomputes the extent by scanning every cell | **fixed** (re-measured 2026-11-12) |
| PERF-06 | P3 | Performance | Packing rewrites the whole zip; threshold packing on the event loop | verified open |
| PERF-07 | P3 | Performance | Structure edits recalculate the whole workbook (~12 s at 100k formulas) | verified open |
| PERF-08 | P3 | Performance | The first chart downloads all of Plotly (4.6 MB) for a bar chart | **new, open** |
| UX-01 | P2 | UX | Menus cannot be operated with the keyboard | fixed (read 2026-11-12, not screen-reader tested) |
| UX-02 | P2 | UX | The grid has no accessible structure | verified open (2026-11-12) |
| UX-03 | P2 | UX | Dialogs do not manage focus | fixed (native `<dialog>`, read 2026-11-12) |
| UX-04 | P2 | UX | Text and border colours fail WCAG contrast | fixed on `bitv`, awaiting commit (residue closed and guarded by a test, 2026-11-13) |
| UX-05 | P3 | UX | No dark mode | fixed (2026-11-12) |
| UX-06 | — | UX | Web menu differs from decisions D4/D5 | needs decision |
| UX-07 | P2 | UX / Web | Website blocks pinch-zoom (`user-scalable=no`) | open; the website is not in this repository (searched 2026-11-13) |
| UX-08 | P3 | UX | Open and Create sit side by side; a typo cannot be told from a wrong password | open |
| UX-09 | P2 | UX | Six web menus against four in D4; the Linux shell maps between them | **new** |
| UX-10 | P2 | UX / Web | An empty server greets everybody as computes, whichever app it serves | **fixed** |
| UX-11 | P2 | UX | The admin sign-in screen had no way back except the browser's Back button | **fixed** |
| UX-12 | P2 | UX | Open dialog goes blank if the server has an access secret | **fixed** |
| UX-13 | P2 | UX | `help_search` leaks one app's topics into another's; composes has none of its own | **fixed** |
| UX-14 | P2 | UX | "Edit this style…" gallery applies and closes on click instead of showing the style to inspect | **fixed** |
| UX-15 | P1 | IO / pptx | The PowerPoint exporter cannot be imported, and loses every colour when it can | **fixed** |
| UX-16 | P2 | UX / Web | A submenu opened by hovering closes again when its item is clicked (File ▸ Manage ▸ …) | **fixed** |
| UX-17 | P2 | UX / i18n | A browser in `en-US` asks for a catalog that does not exist; in `de-DE` it stays English with no language ticked | **fixed** |
| UX-18 | P2 | UX / computes | The formula hint covers the column letters exactly when a whole column is to be picked | **fixed** |
| UX-19 | P2 | UX | Picking the caret's own style back in the gallery pins it: a deviation is then not offered a name, and the next change goes to the old style everywhere | **fixed** |
| UX-20 | **P1** | UX / AI | The AI in computes does nothing and points at an act/suggest switch no client has | **fixed** 2026-11-12 |
| UX-21 | P2 | UX / AI | The chat promises `@ai` where no AI answers (creates), and the refusal names a missing switch | **new, open** |
| UX-22 | P2 | UX | The history speaks three dialects: one per app | **new, open** |
| UX-23 | P3 | UX | Panel layout and undo placement differ between the three apps | partly fixed 2026-11-12 (the suggestion list is gone from above the tabs) |
| UX-24 | P1 | UX / creates | A named style could not be applied to another text box from where people look for it | **fixed** 2026-11-12 |
| UX-25 | P3 | UX / creates | All styles… counted every style's uses as "shapes" when a shape was selected | **fixed** 2026-11-12 |
| UX-28 | P2 | UX / BITV | The page declares no language (WCAG 3.1.1) | fixed on `bitv`, awaiting commit |
| UX-29 | P2 | UX / BITV | A keyboard user cannot leave the grid, nor skip the menus and toolbar (WCAG 2.1.2, 2.4.1) | fixed on `bitv`, awaiting commit |
| UX-30 | P3 | UX / BITV | The tab title does not name the document (WCAG 2.4.2) | fixed on `bitv`, awaiting commit |
| UX-26 | P2 | UX | The AI mode switch: the unchosen half invisible in the light theme, and the switch below the history | **fixed** 2026-11-12 |
| UX-27 | P3 | UX / creates | A new object lands exactly on the previous one, so the second hides the first | **new, open** |
| PROC-01 | P1 | Process | No CI workflow in the repository | fixed (verified at `54d1245`) |
| PROC-02 | P2 | Process | The quality gate prints "everything is clean" when half of it was skipped | fixed |
| PROC-03 | P2 | Process | Work described as delivered is not in the repository | fixed |
| PROC-04 | P1 | Process / CI | CI's Python job fails on every OS: "e2e greeting" skips and `--ci` does not allow it | **fixed** |
| PROC-05 | P2 | Process / CI | CI's web type check checks nothing (`vue-tsc --noEmit` over a `files: []` tsconfig) | **fixed** |
| PROC-06 | P2 | Process / CI | No CI job runs a browser or the Windows client; the `web/e2e` scripts had rotted unnoticed | **fixed** |
| PROC-07 | P3 | Process / tests | A performance guard measures the garbage collector and fails now and then | **fixed** |
| PROC-08 | P3 | Process / tests | A test of the gate fails on every machine where `npm install` has been run | **fixed** |
| PROC-09 | P1 | Process / CI | Two branches both released claudia-core 0.13.0; the gate fails on the duplicate | **fixed** 2026-11-12 |
| PROC-10 | P1 | Process / CI | The Sphinx build fails: `Budget`, `Lens`, `Recorder` are in signatures but not in the reference | **fixed** 2026-11-12 |
| PROC-11 | P2 | Process / CI | The LibreOffice check broke silently: its job may fail and nothing else runs its code | **fixed** 2026-11-12 |
| PROC-12 | P1 | Process / CI | The Linux client's end-to-end test reads the page address before the page starts loading | **fixed** 2026-11-12 |
| PROC-13 | P2 | Process | Nothing pins Python 3.14: `uv` takes 3.15 where it is installed, and OpenVINO cannot be installed there | **fixed** 2026-11-12 |
| PROC-14 | P2 | Process / CI | Two web browser scripts fail on `main` (a stale selector, and UX-20) | **fixed** 2026-11-12 |
| PROC-15 | P2 | Process | The tracker and the backlog lag the code: fixed items still "open", 64 stories at a placeholder 50 % | **new, partly fixed** |
| PROC-16 | P3 | Process / tests | The undo performance guard measured one sample and failed now and then | **fixed** 2026-11-12 |
| PROC-17 | P2 | Process / CI | `web/e2e/demo.cjs` fails again once the client sends *suggest*: it never switched to *act* | **fixed** 2026-11-12 |
| CODE-01 | P2 | Code | No coverage, no web lint; Playwright not declared | **fixed** |
| CODE-02 | P3 | Code | 26 build files tracked in `web/dist` | fixed |
| CODE-03 | P3 | Code | README is out of date | open (not re-checked) |
| CODE-04 | P3 | Code | Untyped functions escape the type check | verified open |
| CODE-05 | P3 | Code | Dead branch in `Gateway.admit`; stale docstring in `state.py` | **fixed** (the branch was not dead: comment corrected) |
| CODE-06 | P3 | Code | `--max-connections` is per document, not per server | open |
| CODE-07 | P3 | Code | `uv.lock.rej` committed at the repository root | fixed |
| CODE-08 | P3 | Code | `ruff format --check` fails; the gate does not run it | fixed |
| CODE-09 | P3 | Code | e2e scripts exist without `package.json` entries | fixed |
| CODE-10 | P1 | Code | `main` at `558f429` has a real `SyntaxError` in 10 files: `except A, B:` instead of `except (A, B):` | fixed |
| CODE-11 | P3 | Code | Windows client: its generated menu is stale, and a test depends on the clone's folder name | **fixed** |
| CODE-12 | P3 | Code | `.gitignore` ignores the tracked `docs/` sources; two test documents are committed | **fixed** |
| CODE-13 | P2 | Code / Perf | `WorkerPool` is built and owned by every hub, and nothing submits work to it | **new, open** |
| CODE-14 | P2 | Code / Arch | The Windows and macOS shells are one design kept as two copies (~1,550 identical lines) | **new, open** |
| CODE-15 | P2 | Code | `./start.sh` kept documents in three layouts and all servers' state in one shared folder | **fixed** 2026-11-12 |
| CODE-16 | P2 | Code / macOS | The macOS client's generated creates menu had no Format ▸ Apply Style…, and nothing checked it | **fixed** 2026-11-12 |
| DOC-01 | P2 | Docs | Decision numbers D70–D82 and D97–D99 are used twice for different decisions | fixed |
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

### SEC-08 · Dependency audits are not run by the gate or CI · P3 · npm fixed 2026-11-11; `pip-audit` open
**Update 2026-11-11.** The npm half is done: `scripts/check_npm_audit.py` is a step of the gate (so also of CI, on every
push and weekly) and audits every `package-lock.json`, development tools included, failing on moderate or worse; the
allow-list is `[[tool.claudia.npm-audit-allow]]` in `pyproject.toml` (empty; a reason is required, an unneeded entry
fails). The findings that had piled up were fixed first (`implementation-notes/implementation-notes-npm-audit-2026-11-11.md`).
Open: the same for the Python dependencies (`pip-audit` or `uv pip audit` against `uv.lock`).
**Evidence (read, `54d1245`).** `scripts/check_debt.py` runs ruff, mypy, vulture, pytest, Sphinx, perf guards and the
web checks. It runs no `npm audit`, no `pip-audit`. `.github/workflows/ci.yml` adds none either.
**Fix.** Add `npm audit --omit=dev` and `pip-audit` (or `uv pip audit`) to the gate, with an allow-list that needs a
written reason per entry.
**Acceptance.** The gate fails on a new high or critical advisory.

### SEC-09 · User names can be confusable · P3 · unverified
**Evidence (read).** `claudia_container.crypto._normalise_name` uses NFKC and `casefold`, which does not fold Cyrillic
`а` to Latin `a`. Only an owner adds users, so the risk is an owner impersonating a colleague in the history.
**Fix.** Reject mixed-script names, or mark two confusable names in one document. Verify with a two-user test first.

### SEC-10 · The AI's method allow-list is enforced in the model parser, not at dispatch · P2 · fixed 2026-11-06
**Evidence (measured, `54d1245`), before the fix.**
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
and E7.6 ("a guarantee that the AI cannot add functions"). Both were enforced by a regex-extracted JSON block filtered
against a name set in a client library, not by the server's authorisation layer where the account is known. Nothing
was remotely exploitable, since every engine in the tree is trusted in-process code, but it becomes serious at two
named milestones — E7.5, which puts document content into the prompt (prompt injection from a cell then chooses method
names), and E3.6/D8, which moves the engine to another machine behind a socket.
**Fix, applied in claudia-server 0.9.0.** `Account.allowed_methods` (`auth.py`): the write methods an account may
call, `None` for an ordinary person. `MethodTable.dispatch` (`protocol.py`) refuses a write method outside it with
`forbidden`, before the method runs — the one place every path goes through: `Assistant._call`, the wire, and any
future remote AI connection. `protocol._apply` separately refuses `account.system` unconditionally, so `apply` cannot
be used as a tunnel around an app's own wrapper checks whatever the allow-list says. `Assistant(allowed_methods=...)`
passes the set on when its account is made; `apps.stand_in_assistant_for` and `apps.model_assistant_for` both set it
from `apps.MODEL_METHODS`, so the scripted stand-in is held to the same guarantee as a real model. `MODEL_METHODS`
gained a `"composes"` entry (`("suggest",)`). `Agent._take_calls` is unchanged: it stays a friendly early message to
the model, not the thing the guarantee rests on.
**Verification.** `test_server_protocol.py` (the mechanism directly: a restricted account may call what is in its
list and nothing else, reading is unaffected, `apply` refuses `account.system` even when `apply` is itself allowed);
`test_server_assistant.py` (end to end, with a rogue engine: `apply`, `chat`, `undo` and `save_checkpoint` are all
refused and change nothing; a composes assistant may `suggest` and nothing else); `test_server_auth.py` and
`test_server_standin_text.py` updated for the new, explicit allow-lists. Full suite green; `uv run python
scripts/check_debt.py --fast` clean (ruff, mypy, vulture, docs, tests) except a pre-existing, unrelated `mypy` failure
in the Linux client (`clients/linux/tests/test_manifest.py`, a `Submenu` union-attr error) — not touched by this fix
and not re-checked here. Not yet re-verified against a commit hash: this round's patch has not been merged.

### SEC-11 · No per-address back-off on failed logins · P3 · verified open
**Evidence (read).** `_Waiting` bounds how many connections wait to be let in, but nothing slows a patient guesser who
logs in once, fails, disconnects and repeats. Named as the remaining part of E2.7 in the security-fix notes.
**Fix.** Per-address and per-(document, name) back-off with a cap, on top of the hashing semaphore.

---
**Re-checked 2026-11-12:** still no back-off, and the new administrator sign-in (`POST /api/admin/login`) has none
either; with SEC-12 fixed it becomes the way in, so it needs the same per-address back-off as documents.

### SEC-12 · Anyone who reaches an exposed server with no administrator can become its administrator · P1 · new, open
**Evidence (measured, `7e619a2`).** `admin_api.py` `setup` needs nothing but a name and a password while
`len(context.admins) == 0`. A server bound beyond loopback (`exposed`: every Docker container, the Scaleway demo) asks
for its first administrator, and the first anonymous visitor wins. Reproduced with
`CLAUDIA_ACCESS_SECRET=… python -m claudia_server --host 0.0.0.0 --no-tls --behind-proxy`: `POST /api/admin/setup`
answered 200 with a session; the access secret is not asked for. As that administrator one can then remove the
access secret (`PUT /settings/access-secret` `null` replaces even the one from the environment), point the AI at any
folder on the machine (`PUT /settings/ai`) and name any executable as `xelatex` (SEC-16). On a platform without a
persistent `/data/state` (the serverless demo) the window opens again on every cold start.
**Fix (not built: recommendation, agreed 2026-11-12).** The usual bootstrap: at start, an exposed server with no
administrator makes a one-time setup code, prints it in its banner and log only (never over HTTP), and `setup`
requires it (constant-time compare; the code dies with the first administrator or at restart). When an access secret
is set, `setup` also requires it. `FirstAdminSetup.vue` gets one field, "Setup code (printed in the server's log)",
mock-up first. Optional: `--admin NAME` / `CLAUDIA_ADMIN_PASSWORD_FILE` to make the first administrator at start, for
deployments. Until then: on the demo, sign up the administrator right after every deploy, or block `/api/admin/` at
the proxy.
**Acceptance.** `test_admin_api`: on an exposed server `setup` without the code → 403, with a wrong code → 403 and the
same time as a right one, with the code → 200 once; with an access secret, the code alone → 403. The banner test shows
the code exactly once.

### SEC-13 · The web app is served without security headers · P2 · fixed 2026-11-12
**Evidence (measured).** `curl -I /` on a server with `--web`: only `cache-control`, `etag`, `content-type`. No
`Content-Security-Policy`, no `frame-ancestors`/`X-Frame-Options`, no `X-Content-Type-Options`, no `Referrer-Policy`.
Any site can frame a document page or the server settings (click-jacking); nothing limits where a script may come from.
**Fix.** In `SinglePageApp` (and the landing page): `Content-Security-Policy: default-src 'self'; connect-src 'self'
ws: wss:; img-src 'self' data: blob:; style-src 'self' 'unsafe-inline'; frame-ancestors 'none'; base-uri 'none';
object-src 'none'`, plus `X-Content-Type-Options: nosniff` and `Referrer-Policy: no-referrer`. Check Plotly and the
typeset images against it in the browser scripts (Firefox and Chromium) before tightening further.
**Acceptance.** A server test asserts the headers on `/`, an asset and `/admin`; the web e2e scripts pass with them.
**Fixed 2026-11-12** in `claudia_server/security_headers.py`, an ASGI layer inside `HostGuard`: the policy above with
`script-src 'self'` plus the SHA-256 of the start page's two inline scripts (Nuxt's import map and runtime config,
read from the build's `*.html` at start, so no `'unsafe-inline'` for scripts), `connect-src` naming the request's own
host for `ws:`/`wss:`, `worker-src 'self' blob:`, `form-action 'self'`, and `frame-ancestors 'self'
http://127.0.0.1:* http://localhost:*` instead of `'none'`, because the Windows and macOS clients show the web app
in a frame of their local shell page (D251); `X-Frame-Options` is left out, as it cannot name two origins. Plus
`Permissions-Policy: camera=(), microphone=(), geolocation=()`. `/api/swagger` keeps only the framing rule while it
loads from a CDN (SEC-14). Tests: `test_server_security_headers.py`. Checked in Chrome for Testing 153: the seven
browser scripts, the Windows and macOS shell windows (the frame), a Plotly chart and the settings page run with no
CSP report, and an injected inline script is refused; the Linux client's end-to-end test (WebKitGTK 6.0) passes
with it. Not yet checked in Firefox.

### SEC-14 · `/api/swagger` loads from a CDN · P3 · new, open
**Evidence (measured).** FastAPI's default page pulls `swagger-ui-bundle.js` and its CSS from `cdn.jsdelivr.net`, so
opening it tells a third party about the server and runs a script from there, against the privacy promise. It is
linked from the landing page and public on every server.
**Fix.** `docs_url=None` by default (`--api-docs` turns it on), or serve the Swagger assets from the package.

### SEC-15 · Office import reads every part whole and parses some XML with defaults · P2 · new, open
**Evidence (read).** `claudia_opc_io.read_parts` and the odf readers `zf.read()` every member with no limit on
uncompressed size or member count: a few-MB zip bomb exhausts the server's memory. Most ODF parsing uses
`XMLParser(resolve_entities=False, no_network=True)`, but `odt.py:235` (styles), `xlsx.py` and
`odf_io/package.py:70` use lxml's defaults (lxml 6 resolves internal entities). Import is not on the wire yet (only
export is), which is why this is P2; it becomes P1 the day the import UI (E2.9, E6.9, E9.5, E10.3) sends a file.
**Fix.** One `safe_parts(data, max_members, max_total, max_ratio)` in `claudia-opc-io` that checks `ZipInfo.file_size`
and the ratio before reading, used by every reader; one module-level hardened `XMLParser` used everywhere.
**Acceptance.** A zip of one 2 GB part of zeros (~2 MB on disk) is refused with a sentence before 50 MB of memory are
used; an entity-expansion document is refused or read without expansion, in each of the six readers.

### SEC-16 · The LaTeX program setting accepts any executable · P3 · new, open
**Evidence (read).** `PUT /api/admin/settings/typeset` stores any path; `resolve_program` accepts any runnable file.
An administrator is trusted, but with SEC-12 that is anyone, and even without it a stolen admin session becomes
"run this binary on every formula". **Fix.** Accept the setting only after the program answers `--version` with an
XeTeX / pdftocairo banner (in the sandbox), and show what it answered on the settings page.

### SEC-17 · A viewer's connection receives the whole history and chat · P2 · open (found 2026-11-05, tracked now)
**Evidence (read, `7e619a2`).** The container gives a viewer no key to history and chat blocks (E2.4), but the live
session ignores roles: `HostedDocument._audience` (`hub.py`) filters events by author, recipient and sender only, and
the `log` and `chat_log` methods (`protocol.py`) answer any account. The 2026-11-05 review described this but it never
got a number, so it was never picked up. **Fix.** In `_audience`, history-bearing events and chat go to editors and
owners only; `log`/`chat_log` refuse a viewer with `forbidden`; the web panel shows a viewer "History and chat are
for the document's editors". Decide first whether a viewer may at least see the *document's* public chat (product
call, not a security one). **Acceptance.** Server tests: a viewer's connection receives no `log`/`chat` event and is
refused `log` and `chat_log`; an editor's is unchanged.

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

**Re-checked 2026-11-12 (`7e619a2`): fixed.** `Sheet.cells_in` keeps a row → sorted-columns index; one 64×16 window
costs 0.11 ms at 10k cells and 0.06 ms at 500k (was 21 ms). Guarded in `test_index_performance.py`.

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

**Re-checked 2026-11-12: fixed.** `Sheet.extent()` is amortized O(1) (`_rows_live`/`_cols_live`); 0.001 ms at 500k
cells.

### PERF-06 · Packing rewrites the whole zip; threshold packing on the event loop · P3 · verified open
**Evidence (documented, E2 slice 3 notes).** Packing writes the whole zip again every 500 changes and at release.
Release runs in a thread; threshold packing does not. Fine up to some tens of megabytes; larger documents need
appending or a split.

### PERF-07 · Structure edits recalculate the whole workbook · P3 · verified open
**Evidence (documented, formula notes).** Inserting a row in a workbook of 100k formulas takes about 12 s: every
formula is rewritten and recalculated. Ordinary edits are incremental and fast (~0.25 ms in a 50k-row workbook).
**Fix.** Rewrite only formulas that refer to the edited sheet; move cells without recompiling.

---

### PERF-08 · The first chart downloads all of Plotly · P3 · new, open
**Evidence (measured).** `ChartView.vue` lazy-loads `plotly.js-dist-min` (good), but that is the full bundle: a 4.6 MB
chunk (`web/.output/public/_nuxt/`), most of it map and 3-D code, for one bar chart. It also carries tile-server URLs
(only used by map traces, never fetched today). **Fix.** A custom Plotly bundle with `bar` (and the next planned
types) via `plotly.js/lib/core` + `plotly.js/lib/bar`, about 1 MB. **Acceptance.** The chart chunk ≤ 1.2 MB, guarded by
a size check in the web job.

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

**Re-checked 2026-11-12: fixed (read).** `MenuBar.vue` now has `aria-haspopup`/`aria-expanded` and arrow-key
handling (commit 47519fa). Not yet tried with Orca or NVDA.

### UX-02 · The grid has no accessible structure · P2 · verified open (the structure is not part of the `bitv` quick fixes)
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

**Re-checked 2026-11-12: still open.** `SheetGrid.vue` has `role="grid"` and still no `row`/`gridcell`,
`aria-rowindex`/`aria-colindex` or `aria-activedescendant`. The grid is the one part of computes a screen-reader user
cannot work with; E5.10 (accessibility baseline) is `todo`.

### UX-03 · Dialogs do not manage focus · P2 · verified open
**Evidence (read, `54d1245`).** `Modal.vue` is a plain element with a global `keydown` listener for Escape. No
`<dialog>`, no `showModal()`, no focus trap, no `inert` on the background, no focus restored to the opener. Every
dialog in the app uses it (Share, Prompt, Help, Styles, Recovery key).
**Fix.** Use native `<dialog>` with `showModal()`, which gives the trap, the inert background and Escape for free;
move focus to the first field; restore focus to the opening control on close.
**Acceptance.** After open, `document.activeElement` is inside the dialog; Tab cycles inside it; after close focus is
on the control that opened it.

**Re-checked 2026-11-12: fixed.** `Modal.vue` is a native `<dialog>` opened with `showModal()` (focus trap, inert
background, Escape).

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

**Re-measured 2026-11-12 (`tokens.css`): mostly fixed.** `--muted` 5.26:1 on white, 5.03:1 on paper, 6.31:1 dark;
`--line-field` ≥ 3:1 in both themes. Residue: creates' `--app-dark` `#b9651c` is 4.25:1 on white, used as normal-size
text (`FooterBar.vue` `.tabs button.on`, `StyleSpec.vue`, `SlideWorkspace.vue`): needs ≥ 4.5:1 (e.g. `#a75a17`). And
`--iris` as text on the dark surface is 2.44:1 — nothing uses it that way today, but nothing stops it. **Acceptance.**
A vitest that reads `tokens.css` and checks every text token against both surfaces, so the next colour cannot regress.

**Fixed on `bitv` (2026-11-13), awaiting commit.** `web/tests/tokens.test.ts` is that vitest (arithmetic in
`web/tests/contrast.ts`). It showed the residue was wider than measured: `--app-dark` is also text on the app's own soft
tint, where computes' teal measured 4.36:1 as well, and the suggested `#a75a17` for creates would have reached only
4.49:1 there. Now teal `#0d7768` (4.73:1 on its soft tint, 4.92:1 on paper) and apricot `#9c5314` (5.05:1, 5.19:1);
composes' `#b8386a` already passed. `--iris` as text on the dark surface stays unfixed and unguarded: nothing uses it.

### UX-05 · No dark mode · P3 · verified open
**Evidence (measured).** `web/app/assets/tokens.css` contains **zero** `prefers-color-scheme` rules, and `--surface` is
a hard-coded `#ffffff`. E0.3 lists a dark/light switch as an acceptance criterion and GNOME apps follow the system
setting. (The server's own fallback landing page in `app.py` does implement dark mode, which makes the gap visible.)
**Fix.** Define dark values for every token, follow the system setting, and let the shell contract pass the OS value.

**Re-checked 2026-11-12: fixed.** `theme.ts` follows `prefers-color-scheme` with a person's override;
`:root[data-theme='dark']` in `tokens.css`.

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

### UX-11 · The admin sign-in screen had no way back except the browser's Back button · P2 · fixed
**Evidence (read, `441d6cb`).** Reported by the owner: opening the connectivity indicator's "Manage this server…"
on a server that already has an administrator lands on `AdminLogin.vue`. `AdminShell.vue` (shown once signed in)
has a `×` "Close" button (`location.href = '/'`); `FirstAdminSetup.vue` has "Skip for now" / "Keep this server
local for now" (`keepLocal()`, same target). `AdminLogin.vue` had neither — nothing in its template emits a way
out, so the browser's own Back button was the only escape. Investigated while trying to reproduce a related report
that a freshly created document seemed to go missing after exactly this click-through-and-Back path; the document
itself turned out fine (D5's "Open creates on the server, Save checkpoints" already means there is no unsaved-draft
window to lose), but this dead end is real and independent of that.
**Fix.** Gave `AdminLogin.vue` the same `close` emit and `×` button `AdminShell.vue` already uses (same markup,
same `.close` styles), and wired it in `AdminApp.vue` to the existing `close()` → `location.href = '/'`.
**Acceptance.** Verified with a real browser against a built app: an administrator account is already configured,
`/admin/` renders the sign-in form with the `×` visible, clicking it returns to `/` (the Open dialog) without
touching browser history.

### UX-12 · Open dialog goes blank if the server has an access secret · P2 · fixed
**Evidence (measured, `441d6cb`).** The backend correctly gates `GET /api/docs` behind the access secret
(`Gateway.accepts_secret`, `app.py`): with one set, the endpoint answers `401 {"detail": "this server needs its
access secret"}`. `OpenDialog.vue`'s `loadServer()` only special-cased a `404` from that fetch; every other status,
401 included, fell into the same branch as success and ran `documents.value = said.documents` — `undefined` for an
error body with no `documents` key. The template's `v-else-if="!documents.length"` then threw
`TypeError: Cannot read properties of undefined (reading 'length')` on render. Confirmed with Playwright against a
real server with an access secret set: page body text came back empty and the console showed exactly that
`TypeError`. This blanks the *entire* Open dialog, not just one document, and needs no editing at all to trigger —
just loading `/` on a secret-protected server. Backlog's E3.9/E3.1 status notes already flagged "the access-secret
prompt" (a way to *supply* a secret from this dialog) as not built; this was the unhandled-exception shape of that
same gap, not a separate missing feature.
**Fix.** Pulled the whole "ask a server for its document list" step into a pure, testable function,
`fetchDocsListing()` in `web/app/lib/open.ts` (mirroring `appOfServer()`'s own extraction for UX-10, and
`admin-api.ts`'s `call()` for how it turns a `detail` field into a message): any non-OK status becomes a
`{ error }` result using the server's own `detail` message when there is one, a 404 keeps its existing wording, and
a 200 whose body has no `documents` array is treated as an error rather than assigned anyway. `OpenDialog.vue` now
calls it and sets `listError` on the error branch, exactly as it already does for the old 404 case — no new UI,
just no longer trusting an unexpected shape. The `Listed` interface moved from the component into `open.ts`
alongside it, since it's now shared.
**Acceptance.** `web/tests/open.test.ts`, `describe('fetchDocsListing', …)`: a normal 200, a 404 (unchanged
wording), a 401 with a `detail` (surfaces it verbatim instead of crashing — this is the regression test), a 500
with no usable `detail` (generic message), a 200 with no `documents` array, and a network failure — seven cases,
all passing. Re-verified live: with an access secret set, `/` now renders the Open dialog's full chrome (servers
sidebar, headline, create-document form) with "this server needs its access secret" where the list would be,
instead of a blank page; zero JS `pageerror`s.

### UX-13 · `help_search` leaks one app's topics into another's; composes has none of its own · P2 · fixed
**Evidence (read + measured, `41f8f39`).** Reported by the owner, four composes inconsistencies in one batch; this
is the help-system one. `core_methods.help_search` (`protocol.py`) called `default_library().search(query)` with
no app at all, so the per-app `apps` front matter every topic file already carries (`help.py`'s `Topic.apps`,
documented since E13.1) was simply never read back out. Confirmed by running a composes document's `help_search`
against the real server code: it returned `computes.writing-a-formula`, `computes.looking-up-a-value` and
`computes.summing-with-a-condition` — three spreadsheet topics, verbatim, inside a word-processor's own Help tab.
The reverse leak (composes' own topics into computes) could not also be demonstrated at this commit because
composes had zero topics of its own — an empty `help/` folder was the second half of the same report: scoping was
missing *and* there was nothing yet to scope.
**Fix.** `HelpLibrary.search(query, *, app=None)` gained the optional keyword: when given, it keeps a topic only
if `app` is in that topic's own `apps`, or `apps` is empty (a topic naming no app is for every app — this is how
`typeset.configure-latex` keeps showing up from every app that can embed LaTeX). `_help_search` now passes
`ctx.document.model.app` along; `_help_topic` is deliberately left unscoped, since an id already names one exact
topic the same way a direct link works from anywhere. This is a Minor, additive change to `claudia_server`'s
public API (`docs/versioning.md`): version 0.18.0 → 0.19.0, changelog entry, snapshot regenerated
(`tests/api/claudia_server.json`). Gave composes its first two topics (`composes.editing-a-style`,
`composes.asking-ai-to-review`) so its Help tab is not merely correctly empty.
**Acceptance.** `packages/claudia-server/tests/test_server_protocol.py`, the `help (E13.1, E13.3)` block: a
computes document's `help_search` never returns composes' own topics and the reverse; a topic naming several apps
(`typeset.configure-latex`) still shows from each of them; `query=""` on a scoped `help_search` gives every topic
for that app, not every topic in the library; composes' own new topics are found by a `style` search;
`help_topic`'s existing behaviour (full text by id, unknown-id error, every role including `ai` can read) is
unchanged, and a new test confirms it is *not* re-scoped — fetching a computes topic's id from a composes document
still works. 10 tests, all passing; the one that depends on composes' own content (`test_help_search_finds_composes
_own_new_topics`) was red before the two topic files existed, green after.

### UX-14 · "Edit this style…" gallery applies and closes on click instead of showing the style to inspect · P2 · fixed
**Evidence (read + measured, `41f8f39`).** Second of the owner's four composes reports. `StyleMenu.vue`'s gallery
click handler called `choose(id)`, which ran `host.apply(id)` — writing the clicked style onto the caret's current
paragraph — and then `emit('close')`. There was no way to look at a style's CSS or controls without first applying
it to whatever the cursor happened to be sitting in, and the menu vanished the instant you clicked, before the
look below it could even be seen. Confirmed by reading `StyleMenu.vue`/`StyleSpec.vue`/`style-host.ts` together:
`StyleSpec.vue` always read `props.host.current`, which is exactly the document's own current style — there was
no separate notion of "the style I am looking at" distinct from "the style under the caret" anywhere in the three
files. `StylesDialog.vue` ("All styles…") and `StyleBar.vue` (the toolbar's quick-apply list) were checked and
confirmed unaffected — neither goes through this gallery-click path.
**Fix.** `StyleEditor` (`web/app/lib/style-host.ts`) gained `pick(id)`, `isPicked` and `canDeviate`: picking a
style only changes what `editor.current`/`editor.look` show, never the document, and the caret's own paragraph is
left untouched. The gallery's click handler now calls `editor.pick(s.id)` directly — no `apply`, no `close`.
Picking a style other than the caret's own forces scope to "every use" and disables "this paragraph only" (there
is no selection to split off from a style that is merely being browsed); this is also how a change made while
picking a style is written — to that style, for everyone, never as a deviation of whatever the cursor is really
in. `StyleMenu.vue` now constructs the one `StyleEditor` and passes it down to `StyleSpec.vue` as a prop (moved
from being constructed locally in `StyleSpec.vue`), so picking in the gallery and the controls below it share the
same state; a small "here" badge marks which gallery row is the caret's real style whenever that differs from
what is being inspected. **Decision taken:** "this paragraph only" is disabled, not merely defaulted away, while
picking another style — the owner's choice between the two when asked.
**Acceptance.** `web/tests/style-editor.test.ts`, `describe('picking a style to inspect, without applying it
(UX-14)', …)`: picking sends nothing to the document and leaves the caret's own style alone; picking forces
"every use" and disables deviation; an edit made while picking changes the picked style, never a deviation of the
caret's own; picking the caret's own style back behaves exactly as not picking at all — 6 new tests, all red
before `pick()` existed, green after; full suite 473/473, `vue-tsc --noEmit` clean. `web/e2e/styling.cjs` gained a
matching browser scenario (pick Heading 1, confirm the paragraph is untouched and the "here" badge appears, edit
while picked changes Heading 1 globally, undo and pick back restores the ordinary controls) — written against the
real component source and existing selectors, but **not executed** in this sandbox: Playwright's browser-binary
download host is outside the sandbox's network allowlist (confirmed via the proxy's own status endpoint). Running
it for real, or in CI where Chromium is already installed, is the one piece of this fix not yet machine-verified.

### Note on PERF-04
While reproducing the above, `bugtracker.md`'s own index still lists `PERF-04` as "fixed (listing cache)", but
`SealedDocuments.documents()` — the provider the real server uses today — globs and re-reads every container
file's manifest on every call (`sealed.py`, `documents()`). No cache currently exists in that path. Not a
correctness bug (the listing is always fresh, which is why neither UX-11 nor UX-12 traces back to a stale cache),
but whatever closed PERF-04 belonged to an earlier, now-replaced store, and the index entry is stale.

---

### UX-16 · A submenu opened by hovering closes again when its item is clicked · P2 · fixed
**Evidence (2026-11-10, `301ded6`).** `e2e/demo.cjs` could not reach File ▸ Manage ▸ Share…. In `MenuBar.vue`,
hovering a flyout parent opens it (`enterItem` sets `activeSub`), and clicking the same parent *toggled* `activeSub`
— so a mouse, which always hovers before it clicks, closed the flyout it had just opened.
**Fix.** A click on a flyout parent only opens it. The keyboard path is unchanged.

### UX-17 · A regional browser locale asks for a catalog that does not exist · P2 · fixed
**Evidence.** Every page in a browser set to `en-US` logged `404 /i18n/en-US.json` (found as console errors by the
e2e scripts). In `de-DE` the same lookup missed `de.json`, so the app stayed English, and Config ▸ App Language
ticked neither entry, because it compared `en`/`de` with the full tag.
**Fix.** `appLanguage(tag)` in `web/app/lib/i18n.ts` maps a tag to an App Language (exact, then by language, then
English); the catalog and the menu use it. Tests in `web/tests/i18n.test.ts` (the no-fetch ones now count calls: a
throwing stub could not tell, because `loadCatalog` swallows errors).

### UX-18 · The formula hint covers the column letters while a formula is typed · P2 · fixed
**Evidence.** `e2e/pointing.cjs` failed now and then on "a whole column from its header": the click landed on
`.formulaHelp`, which appears under the formula bar exactly over the column letters while `=SUM(` is being typed.
**Fix.** The hint takes no pointer events; it only reads.

### UX-19 · Picking the caret's own style back pins it · P2 · fixed
**Evidence.** `e2e/styling.cjs`: after looking at Heading 1 and picking Body text back (UX-14's gallery), making the
paragraph bold "this paragraph only" created the new style, but the menu stayed on Body text — no invitation to name
the new style, and the next change went to Body text for everyone.
**Fix.** `StyleEditor.pick` treats the caret's own style as "follow the caret again". Test in
`web/tests/style-editor.test.ts`.

### UX-20 · The AI in computes does nothing and points at a switch no client has · P1 · fixed 2026-11-12
**Evidence (measured, `7e619a2`).** `web/e2e/demo.cjs` failed at "ai done": `@ai build an example budget` was
answered "You asked me in suggest mode … Switch to act mode". No client sends `ai_mode` yet, and `ai_mode.parse_mode`
read a missing mode as *suggest*, although `chat`'s own description and the E7.7 build note say "a client that sends
none gets act"; computes cannot propose yet (E7.8), so the AI wrote nothing, ever. **Fix (agreed 2026-11-12).**
`UNSAID_MODE = ACT` for a request without a mode; `DEFAULT_MODE` stays *suggest* for a client with the switch (D262).
Tests in `test_server_ai_account.py`; `demo.cjs` passes again.

### UX-21 · The chat promises an AI where none answers · P2 · new, open
**Evidence (measured, screenshots of `slides.cjs`).** creates' chat says "Write to everybody, or @ai to ask the
assistant. Say @ai help to see what it can do", but creates has no AI user (no `ai` avatar; E7.9 is `todo`). Until
UX-20 the computes refusal also named "act mode", a switch that exists in no client. **Fix.** The hint comes from what
the server says it has (`hello`/`people` already list `ai`): no `ai` participant, no `@ai` in the hint. Any message
that names a control must name one the person can see. **Acceptance.** A web unit test of the chat hint with and
without an `ai` participant.

### UX-22 · The history speaks three dialects · P2 · new, open
**Evidence (measured, the three apps side by side).** computes: `ann A1 = Item`, `add sheet Sheet1` (terse, formula
style); composes: `typed "…"`, `new paragraph`, `style title`, `changed the style heading-1…` (lower case, ids instead
of names); creates: `Added a text box`, `Wrote Hello slide`, but `Add shape` (capitalised, past tense and imperative
mixed). The panel tab says "History & Chat", the header button "History & chat". **Fix.** One rule in the design
system (`notes/design-system.md`): past tense, lower case, the thing's *name* not its id, the value last; e.g.
`added a text box`, `added a circle`, `set A1 to Item`, `changed the style Heading 1`. The label strings live in one
place per app (`describe` of each command), so this is a wording pass plus a test that every command kind has a
description in that form. **Acceptance.** A test per app that walks every command kind's description.

### UX-23 · Panel layout and undo placement differ between the apps · P3 · new, open
**Evidence (screenshots).** In composes the suggestions sit above the History & Chat / Help tabs, so the tabs move
to the middle of the panel; in computes and creates they are at the top. Undo/redo: in the formula bar on the left
(computes), at the right end of the insert bar (creates, with Delete), absent from the bar in composes. The decided
History filter row (All / Conversation / Changes) is not built yet. **Fix.** Tabs always at the top; composes'
suggestions become a section inside "History & Chat" (or a third tab only in composes, by decision); undo/redo in the
same place in all three bars, mock-up first (`notes/mockups/`).

## Process and code

### UX-10 · An empty server greets everybody as computes, whichever app it serves · P2 · fixed
**Evidence (measured, `22d5fe4`).** `./start.sh all` runs three servers — computes 8765, composes 8766, creates 8767.
All three landing pages showed the computes headline, "Think with your data. Open a table, or start a new one", and
the top bar said only "claudia". Opening a document on each port gave the right app every time, so the servers and
the launcher were never wrong; only the greeting was. The effect was worst on a fresh machine, where every folder is
empty and all a person sees is three identical pages claiming to be the table app.
**Cause.** `OpenDialog.vue` worked the app out as `documents.value[0]?.app ?? 'claudia'` — from the *first listed
document*. With no documents there was nothing to read, and the copy fell through to the computes wording, which is
the fallback branch. `/api/docs` has answered `{"app": ..., "documents": [...]}` all along; the page took the
documents and dropped the app.
**Fix.** `appOfServer()` in `web/app/lib/open.ts`: believe the server, fall back to a listed document for an older
server that does not say, then to claudia in general. Extracted into `lib` rather than left in the component so it
could be tested — the web tests cover `lib`, and there is no component harness. Four tests in `web/tests/open.test.ts`.
Re-measured on all three ports with empty document folders: computes says "Think with your data", composes "Write
together", creates "Say it on a slide", and each top bar names its own app.
**Acceptance.** `tests/e2e/test_greeting.py` — the first test in the project that drives a real browser. It runs
`./start.sh all`, opens each of the three ports in Chromium and reads `data-app` and the headline off the page.
Confirmed to fail on `22d5fe4` for the right reason before the fix (all three said `app: claudia` and "Think with
your data"), and to pass after it. `scripts/check_debt.py` runs it as the `e2e greeting` step and skips it, saying
which is missing, where the web app is not built or there is no Chromium; CI has an `e2e` job that installs both.
**Why nothing caught it.** Every layer below the rendered page was correct — the launcher, the three servers,
`/api/docs` — and the web tests cover `web/app/lib`, not the page. The bug lived in the one place nothing looked.
**Not the cause, though it looks like one.** computes and creates show "No styles yet" under *Format*: those menus
are deliberately inert (D125) and the style UI for both is still to come.

### UX-15 · The PowerPoint exporter is dead, and loses every colour once it is not · P1 · fixed
**Evidence (measured, `441d6cb`).** `import claudia_creates_io.pptx` raised `ImportError: cannot import name
'Style' from 'claudia_creates'` — so every .pptx export and import failed on the first call, and nine of the
package's own tests failed. `ruff` had three errors at this commit for the same reason, and the catalogue's
`pptx-*` and `docx-*` entries were failing too.
**Cause.** Two branches met. The shared object layer (D177) removed creates' own `Style` dataclass, turned
`SlideObject` into a PEP 695 type alias — which cannot be called — and made an object's words a frozen
`Paragraph` whose runs must cover its text exactly (D181). The additive-io branch was written against the flat
object it replaced: it imported `Style`, called `SlideObject(...)`, read `.kind/.x/.text/.style` off a
`VisualObject`, indexed `BUILTIN_STYLES` as if it were a dict, and its tests and the catalogue's `spec.py` files
did the same. Nothing caught it because neither branch's own gate ran against the other's code.
**And a quieter one behind it.** Once it imported, `slides_to_pptx` read `computed` CSS and looked for a
`#rrggbb`. Since D201 every built-in style names a role: `fill: @accent/14` holds no hex, `_rgb` found none, and
the fill and the border were dropped silently. A deck exported from a brand-new presentation came out colourless.
**Fix.** The import half was fixed on `main` independently (the `xlsx-docx-pptx-additive-io` merge, #23): the
importer builds a body and an anchor, `apply_edits_to_pptx` reads `.body`/`.anchor`, and the catalogue's
`spec.py` files were rewritten the same way. When `shapes-n-images` was rebased onto `main` (2026-11-10) `main`'s
version of all of that was kept and this branch's duplicate (`_object`, `claudia_test_documents.edits`) dropped.
What this branch adds on top is the colour half: both `slides_to_pptx` and `apply_edits_to_pptx` resolve against
the document's own style book and palette (`_look`) instead of reading `computed`; `_rgb` reads `rgb()` and
`rgba()` as well as hex, and flattens a translucent colour over the palette's `page`, because a solid pptx fill
has nowhere to keep an opacity and dropping the 14% would export a pale wash as full-strength iris (D211).
**Two regression tests** pin the part no test covered: that a shape's colours reach the file at all, and that
changing a role changes what the file holds.
**Why nothing caught it.** The two branches were each green on their own. A merge that is clean to git can still
be broken in Python — a removed name, an alias that stopped being callable, a dataclass that became frozen — and
nothing runs the other side's tests until both are on one branch.

### PROC-01 · No CI workflow in the repository · P1 · fixed
`.github/workflows/ci.yml` exists at `54d1245`: a Python matrix over ubuntu, windows and macos running
`scripts/check_debt.py`, a web job (`npm ci`, `nuxt prepare`, `vitest`, `vue-tsc`), a Monday schedule and
`workflow_dispatch`. Whether it has ever run green on Windows and macOS is still unknown from the tree alone.

### PROC-02 · The quality gate prints "everything is clean" when half of it was skipped · P2 · fixed
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
**Fixed.** `check_debt.py`'s `verdict()` never reports "clean" over a skip — the summary is "clean except skipped: …"
whenever anything skipped, named, whether or not `--ci` allow-lists it. `--ci` turns any *unlisted* skip into a
failure. `ci.yml`'s Python job now runs `check_debt.py --ci --allow-skip "web tests" --allow-skip "web types"
--allow-skip "linux client tests"` — exactly the three checks the separate `web` and `linux-client` jobs cover for
real on their own runners; any other skip still fails the build. (D133)
**Acceptance — met.** `tests/test_check_debt.py::test_ci_catches_the_real_bug_with_no_node_modules` feeds this
checkout's own real skip (no `web/node_modules`) through `verdict(..., ci=True, allow_skip=set())` and asserts it
fails — the bug's own reproduction, now a standing regression test.

### PROC-03 · Work described as delivered is not in the repository · P2 · fixed
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
**Fixed.** The owner rebuilt and committed the E6.3 pointing work directly (confirmed in the tree at `13d1c80`:
`web/app/lib/pointing.ts`, 22 cases in `web/tests/pointing.test.ts`, the nine-case `web/e2e/pointing.cjs`), so this
round's patch covers only the second half: the rule that a note may only say "built" with the commit that carries it
(status lives in `backlog.md`, derived from the code), and the cheap guard —
`tests/test_notes_claim_built_files.py` greps every "built" paragraph under `claudiaoffice-log/` for a root-relative
path and fails if that path is not in the tree. `e4-e6-formulas-notes.md` and `backlog.md`'s E6.3 card are corrected
to match what is now actually in the tree.
**Acceptance — met.** The claim is true in the tree (`13d1c80`) and the note and `backlog.md` match it; the new guard
would have caught the original false claim (proved by temporarily reintroducing it and watching the test fail).

### CODE-01 · No coverage, no web lint; Playwright not declared · P2 · fixed (2026-11-10)
**Evidence (read, `54d1245`).** No `pytest-cov` or coverage settings in `pyproject.toml`; no eslint, prettier or Biome
in `web/package.json`; the `e2e` scripts run `node e2e/*.cjs`, which needs Playwright, and Playwright is not in
`devDependencies`.
**Why it matters.** `CONTRIBUTING.md` promises TDD. Without a coverage number and a trend there is nothing to check
that promise against — and the test suite is large enough (≈1,321 Python tests, 195 web tests) that the question is
now about where the gaps are, not whether tests exist.
**Fix.** `pytest-cov` with a floor per package, starting at the measured value and ratcheting up; a linter for `web/`;
declare Playwright.
**Done 2026-11-10.** Playwright was declared in the QA round. The gate's `tests` step now runs with `--cov` (it costs
nothing measurable on Python 3.14) and a new `coverage` step holds each of the fifteen packages to a floor in
`pyproject.toml` (`scripts/check_coverage.py`, `--ratchet` to raise them), from 83% (composes) to 100% (opc-io). The
floors are held on Linux with TeX, where every test runs; the check skips elsewhere and CI allows that skip only off
Linux. `web/` has ESLint (`@nuxt/eslint-config`, no stylistic rules; 172 findings fixed or turned off with a reason)
and `npm run coverage`, which holds `app/lib` to thresholds of 88% statements, 90% branches, 80% functions. Both run
in the gate and in CI's `web` job. Notes: `implementation-notes/implementation-notes-coverage-and-lint.md`.

### CODE-02 · 26 build files tracked in `web/dist` · P3 · fixed (2026-11-10)
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

### CODE-05 · Dead branch in `Gateway.admit`; stale docstring in `state.py` · P3 · fixed (2026-11-10)
**Evidence (read, `54d1245`).** `app.py` lines 232–235 still hold the branch commented "(cannot happen; keeps verify's
checks)".
**Fix.** Remove the branch with its test, or replace the comment with an assertion that states the invariant.
**Update 2026-11-10.** The branch is not dead: the user directory is kept apart from the documents, so a creation that
died between adding the owner and writing the document leaves an account behind; `test_server_gateway_threads.py`
reaches it with a directory that knows the user. An assertion broke that test. The comment now says what the branch
is for. The `state.py` half is still open.
**Update 2026-11-10, later.** `state.py` said the folder held the server's "encryption key and its TLS certificate".
There is no server-wide encryption key — document keys live in memory only (`sealed.py`) — and the folder also holds
the admin settings and the list of administrators (`admin/`). The docstring now lists what is there and why it is
kept apart from the documents; `--state-dir`'s help said "its certificate" only and was corrected the same way.

### CODE-06 · `--max-connections` is per document, not per server · P3 · open
Rename to `--max-connections-per-document`, document it, and keep the server-wide caps from SEC-02 separate.

### CODE-07 · `uv.lock.rej` committed at the repository root · P3 · fixed
**Evidence (measured).** `uv.lock.rej` is tracked at the root: rejected hunks from a failed `git apply` of a lock-file
update. It shows two things that did not land: `claudia-creates` as a dependency of `claudia-server`, and a
`cryptography` floor moving between `>=43` and `>=44`.
**Why it matters.** CI runs `uv sync --locked`, so a lock file that disagrees with the package metadata fails the build
for everyone. The `cryptography` floor is not cosmetic: Argon2id first appears in `cryptography` 44, and the container
depends on it, so a `>=43` floor allows an install that cannot open a document.
**Fixed.** `uv.lock.rej` deleted (and its deletion staged); `claudia-server`'s `pyproject.toml` floor corrected to
`cryptography>=44`; `uv.lock` regenerated with `uv lock` — its `claudia-server` block now correctly lists
`claudia-creates` as a dependency.
**Acceptance — met.** `uv sync --locked` succeeds from a fresh clone; `git ls-files '*.rej' '*.orig'` is empty; the new
`tests/test_repo_hygiene.py::test_no_rej_or_orig_files_are_tracked` fails the gate if a `.rej` or `.orig` file is ever
tracked again.

### CODE-08 · `ruff format --check` fails; the gate does not run it · P3 · fixed
**Evidence (measured, `54d1245`).** `uv run ruff format --check .` reports **1 file would be reformatted**
(`docs/conf.py`). `scripts/check_debt.py` runs `ruff check` but never `ruff format --check`, so the repository has no
enforced format and the drift is invisible.
**Fixed.** `docs/conf.py` reformatted; `ruff format --check .` added to `check_debt.py` as its own named check
("ruff format"), distinct from "ruff" (D133). `pyproject.toml` also excludes `claudiaoffice-log` from ruff's scope —
an illustrative code fence in a notes file was tripping the formatter with no source to fix.
**Acceptance — met.** `tests/test_check_debt.py::test_ruff_format_is_its_own_check` asserts the gate runs it as a
named check; `uv run ruff format --check .` now passes clean.

### CODE-09 · e2e scripts exist without `package.json` entries · P3 · fixed (2026-11-10)
**Evidence (measured).** `web/e2e/` holds `composes.cjs`, `demo.cjs`, `recovery.cjs`, `resilience.cjs`, `slides.cjs`
and `styling.cjs`. `web/package.json` has scripts for only four of them: `e2e`, `e2e:composes`, `e2e:slides`,
`e2e:resilience`. `styling.cjs` and `recovery.cjs` — the scenarios for the two newest features — can only be run by
typing the path.
**Fix.** Add `e2e:styling` and `e2e:recovery`, or one `e2e:all`; and a test that every file in `e2e/` has a script.

### CODE-10 · `main` at `558f429` has a real `SyntaxError` in 10 files: a buggy `ruff format` landed invalid syntax · P1 · fixed
**Evidence (measured, a fresh clone of `main` at `558f429` — "QA finding fixed: quality signals work", the commit
that landed D133/CODE-08).** Ten files parse with `python3 -c "import ast; ast.parse(open(f).read())"` to a real
`SyntaxError: multiple exception types must be parenthesized`, not a lint opinion:
`docker/healthcheck.py`, `packages/claudia-client/src/claudia_client/trust.py`,
`packages/claudia-computes/src/claudia_computes/formula/forms/reference.py`,
`packages/claudia-computes/src/claudia_computes/formula/operators.py`,
`packages/claudia-computes/src/claudia_computes/functions/base.py`,
`packages/claudia-computes/tests/test_computes.py`, `packages/claudia-core/tests/helpers.py`,
`packages/claudia-creates/tests/test_slides.py`, `packages/claudia-typeset/src/claudia_typeset/cache.py`,
`scripts/api_surface.py`. Every one is the same shape:
```
-        except (OSError, ValueError):
+        except OSError, ValueError:
```
`except A, B:` is Python 2 syntax; Python 3 refuses to parse it at all. `pyproject.toml` pins `ruff>=0.6` with no
upper bound, and `uv.lock` resolves **ruff 0.17.3** (2026-10-27); fed the valid, already-parenthesized form, this
`ruff` version's formatter reformats it into the invalid form above — confirmed directly with
`uv run ruff format --diff` on each file in isolation. This is almost certainly how it got into `main`: CODE-08's own
fix ran `ruff format .` to reformat `docs/conf.py`, and a real (non `--check`) run touches the whole tree, so the
same bug struck these 10 unrelated files and the broken result was committed alongside the intended fix. CODE-08's
"`ruff format --check .` now passes clean" was true only against whichever `ruff` resolved at that moment —
`ruff>=0.6` let a later, regressed release drift underneath it before anyone ran the check again.
**Why it matters.** This is not a style nit: a fresh checkout of `main`, exactly as the owner asked this round's work
to start from, fails to import `claudia_client.trust`, three `claudia_computes` modules, and the rest, in whatever
runs them first. It was caught only because this round's own gate run (`check_debt.py`, with CODE-08's check now
actually exercised) flagged `ruff format` as failing and the diff looked backwards from a real fix.
**Fixed.** The parens are restored in all 10 files; each now parses and matches its pre-breakage, correct form.
Bisected every published release: 0.6–0.14.x format this correctly, every 0.15.0–0.17.4 (the latest) strips the
parens — no upstream fix exists yet. `pyproject.toml` now pins `ruff>=0.6,<0.15`; `uv lock` resolved **0.14.14**,
which also wanted two small, unrelated, pre-existing reformats (a docstring's trailing space before `"""`, a blank
line after a `def`) — applied with `uv run ruff format`, since those two are genuinely correct under the pinned
version and not the bug.
**Acceptance — met.** The 10 files parse (`ast.parse`) and keep `except (A, B):`; `uv run python
scripts/check_debt.py --ci --allow-skip "web tests" --allow-skip "web types"` — CI's own invocation — exits 0, with
`ruff format: ok`.

### CODE-11 · Windows client: stale generated menu, and a test that depends on the folder name · P3 · fixed
**Evidence.** `generate_menu.py composes --check` failed (the manifest gained App Language and more since the file was
generated), and `defaultRepo` was tested with `endsWith('claudia')`, which fails in a clone called anything else.
**Fix.** Menus regenerated for all three apps (`--all`, as `npm run generate-menu` does); the test checks what is in
the folder instead of its name.

### CODE-12 · `.gitignore` ignored the tracked `docs/` sources · P3 · fixed
**Evidence.** `.gitignore` listed `docs` (meaning a documents folder), which matches `docs/`, the Sphinx sources: a new
page there would silently not be added. `docs-computes/docs/test125.claudia(.journal)` were committed although
`docs-*` is ignored, and the Obsidian line ignored plugin files that are tracked on purpose.
**Fix.** `.gitignore` rewritten by topic: `docs/_build` only, `web/dist` added (CODE-02), only Obsidian's per-person
`workspace*.json` ignored. The two test documents and `web/dist` are untracked.

### DOC-01 · Decision numbers are used twice for different decisions · P2 · fixed
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
**Fixed.** `decision-log.md` keeps the product numbering (it was first and is cited most widely); the E2 block moved
to **D100–D112** and the native-client block to **D113–D119**, with a mapping table in the log so old references
resolve. The code citations are now updated to match: `claudia_container/__init__.py`, `container.py`, `crypto.py`,
`slots.py`, `journal.py`, `passwords.py` and their tests, plus `CHANGELOG.md`; `claudia_server/auth.py`, `sealed.py`
and its test. `claudia-creates` and `claudia-server/composes.py` needed no change — both already cited D73/D75 in
their canonical (post-collision) meaning, styling-is-CSS, not the colliding one.
**Acceptance — met.** `tests/test_decision_log.py` adds two checks: no row in `decision-log.md` is allocated twice,
and every `D<number>` cited anywhere in `packages/`, `clients/`, `web/`, `scripts/`, `tests/`, `docs/` and the root
changelogs resolves to exactly one row (it deliberately excludes `claudiaoffice-log/` itself, which is the log and its
own historical account of the collision).

---

### PROC-04 · CI's Python job fails on every OS · P1 · fixed
**Evidence (2026-11-10, `301ded6`).** Run exactly as `.github/workflows/ci.yml` runs it, `check_debt.py --ci` ends
"FAILED: e2e greeting": the browser test (UX-10) skips where the web app is not built, and the job allowed only the
web and Linux-client skips. No job ran the browser test either.
**Fix.** The Python job allows that skip; the new `e2e` job runs it for real (PROC-06).

### PROC-05 · CI's web type check checks nothing · P2 · fixed
**Evidence.** `web/tsconfig.json` is `files: []` plus references to the generated projects, so `npx vue-tsc --noEmit`
(without `-b`) type-checks no file: with `export const broken: number = "x"` added it still exits 0, while
`npm run typecheck` (`nuxt typecheck`) exits 2. The type error in `Workspace.vue`'s `chartInserted` passed CI this way.
**Fix.** The web job runs `npm run typecheck`, as the gate does.

### PROC-06 · No CI job ran a browser or the Windows client · P2 · fixed
**Evidence.** Neither `tests/e2e` nor any `web/e2e/*.cjs` script ran anywhere, and Playwright was not a declared
dependency of `web/` (CODE-01). All seven scripts failed on `main`: six on selectors from before the connection
indicator and File ▸ Manage existed, one on a toast for formulas "not there yet". Behind them were four real bugs
(UX-16 to UX-19). The Windows client's 63 vitest tests and its menu `--check`, which its own docstring says "a CI job
runs", ran nowhere; one test and the generated menu were broken (CODE-11).
**Fix.** New `e2e` job (Chromium; `tests/e2e`, then the five scripts against `./start.sh all`, then the two that start
their own server; screenshots kept on failure) and `windows-client` job (vitest, `tsc`, menu `--check`, the tool's
pytest). The scripts were brought up to date and all pass.

### PROC-07 · A performance guard measures the garbage collector · P3 · fixed
**Evidence.** `test_opening_from_a_snapshot_is_linear_in_the_formulas` failed with 25.07x against its 25x bound.
Measured: 800 → 8,000 formulas takes 20–25x with the cyclic collector on and 11x with it off — a collection is
triggered by how much is allocated, so it lands in the large case.
**Fix.** Both timing helpers (`claudia-core`, `claudia-computes`) hold the collector off while timing, as `timeit`
does.

### PROC-08 · A test of the gate fails wherever `npm install` was run · P3 · fixed
**Evidence.** `test_ci_catches_the_real_bug_with_no_node_modules` asserted that *this checkout* has no
`web/node_modules`, so it failed on every developer machine and passed only in CI.
**Fix.** `web_checks()` takes the web folder; the test points it at an empty one.

### PROC-09 · Two branches both released claudia-core 0.13.0 · P1 · fixed 2026-11-12
`ai_server` added `Document.scratch` as 0.13.0 while `styling-suite` had released 0.13.0 and 0.14.0; the merge kept
both 0.13.0 headers and `_version.py` at 0.14.0, so `test_changelog_versions.py` failed the gate. Renumbered the
scratch release 0.15.0, raised `_version.py`, regenerated `tests/api/claudia_core.json`, fixed the reference in the
E7.8 story. **Prevention:** the version is the last thing a branch sets, after merging `main` (CONTRIBUTING).

### PROC-10 · The Sphinx build fails on three unresolved types · P1 · fixed 2026-11-12
`ModelEngine`'s signature names `model_engine.Budget` and `lens.Lens` (and `Lens.recorder` names `lens.Recorder`);
none was in `docs/api/claudia_server.rst`, and `nitpicky` turns that into an error. Added the three under
"Assistant".

### PROC-11 · The LibreOffice check broke silently · P2 · fixed 2026-11-12
`scripts/odf_libreoffice_check.py` built its deck by hand and gave a shape's words the outline style `plain-shape`;
since D310/D316 an outline cannot style words, so `new_deck()` raised. Its CI job is `continue-on-error` and nothing
else ran the script, so nothing turned red. It now takes the styles the server gives a new object
(`STYLE_OF_KIND`, `PARAGRAPH_STYLE_OF_KIND`), and `tests/test_odf_libreoffice_check.py` builds the three new files and
every library case in the normal suite, without LibreOffice. Verified with LibreOffice 24.2: 31 of 31 read.

### PROC-12 · The Linux client's end-to-end test reads the address too early · P1 · fixed 2026-11-12
Since the page cache is emptied before every load (`WebPage._load_current`, asynchronous, commit 08ffcb9) the window
shows the web view before the view has an address, and `view.get_uri()` is `None` for a moment. The test now waits for
the address. 558 passed, 6 skipped under `xvfb-run` on Python 3.12 with GTK 4 and WebKitGTK 6.0.

### PROC-13 · Nothing pinned Python 3.14 · P2 · fixed 2026-11-12
`requires-python = ">=3.14"` lets `uv` take the newest Python it finds; with 3.15 on a machine the environment was
made with it, and `openvino-genai` has only cp314 wheels and no sdist in `uv.lock`, so `--ai` could not be installed.
`.python-version` (`3.14`) now decides, and `tests/test_python_version.py` keeps it, every `requires-python`, the CI
workflows, the Dockerfile and `build-deb.sh` on the same version.

### PROC-14 · Two browser scripts fail on `main` · P2 · fixed 2026-11-12
`web/e2e/styling.cjs` read the gallery's font weight from `.name`; the look moved to `.name .look`. `demo.cjs` failed
on UX-20. All seven scripts and `tests/e2e` pass against `./start.sh all` (Chrome for Testing 153).

### PROC-16 · The undo guard measured one sample and failed now and then · P3 · fixed 2026-11-12
`test_undoing_the_latest_step_does_not_depend_on_the_history_before_it` (claudia-core perf) timed a single run of 50
undos and failed once in this round at 4.04x against a 4.0x limit (0 of 15 reruns). Undo uses up its steps, so it could
not repeat on one document; it now takes the best of three fresh documents per size. Same kind as PROC-07.

### PROC-15 · The tracker and the backlog lag the code · P2 · new, partly fixed
**Evidence.** In this file PERF-01, PERF-05, UX-01, UX-03 and UX-05 were "verified open" although fixed in the tree
(corrected above). In the backlog, E7.7 is `todo`, 0 % with a "Built 2026-11-11" paragraph; 64 of 90 stories that are
`in-progress` sit at exactly 50 %, which the README calls "an estimate from the code, not from hope" — 50 is a
placeholder. **Fix.** A branch that fixes a tracked item changes its row in the same commit (CONTRIBUTING rule);
`test_backlog.py` could refuse `progress: 50` on a story without a status-evidence paragraph.

### CODE-13 · `WorkerPool` has no callers · P2 · new, open
**Evidence (read).** `workers.py` (E3.5) says it exists for PERF-02 and D37, `Hub` makes one and stops it, but nothing
in `packages/*/src` calls `submit`. Meanwhile every edit still `fsync`s on the event loop (PERF-02) and threshold
packing runs there (PERF-06). **Fix.** Either use it — journal append and packing via `asyncio.to_thread` (I/O, a thread
is enough), formula recalculation of large structure edits via the pool (PERF-07, E4.4) — or remove it until a caller
exists. **Acceptance.** A test that a slow `fsync` (monkeypatched to sleep 50 ms) on one document does not delay a
`cells` request on another.

### CODE-14 · The Windows and macOS shells are one design kept as two copies · P2 · new, open
**Evidence (read, `d696927`).** At `7e619a2` the Windows shell (7 files, 975 lines) had none of macOS's connection,
trust or server list. The branch `win-client-complete` (merged as `d696927`) rebuilt it on the macOS design, which
closes that feature gap, by copying: `clients/windows/src` and `clients/macos/src` now have the same 22 file names,
11 of them byte-identical (bridge, connection, connector, contract, core, core-entry, core-protocol, extension,
servers, settings, shell-page-entry: about 1,550 lines) and the rest differing only where the OS does
(paths, launch, server, menu). Every fix to the shared part now has to be made twice, and nothing checks that it is.
**Recommendation:** move the identical files into one `clients/neutralino/` package (or `clients/shared/`) that both
build from, keeping per-OS `paths`, `launch`, `server`, `menu`; until then, a test that the shared files stay
byte-identical, so a fix in one copy fails the build until it is in the other.

### CODE-15 · `./start.sh` folder layout · P2 · fixed 2026-11-12
**Evidence.** Documents in `<repo>/docs-<app>` (before 2938f0a: `demo-docs`, `demo-docs-<app>` — the folders people
still find), `--dir X` meaning X for one app but `X/<app>` for `all`, and no `--state-dir`, so the three dev servers
shared one certificate and one administrator list in `~/.local/share/claudia`, the tree where the Linux desktop app
keeps `~/.local/share/claudia/<app>/documents`. **Fix (agreed 2026-11-12).** `.claudia/<app>/documents` and
`.claudia/<app>/state` per checkout (ignored); `--dir DIR` means `DIR/<app>/…` always; old folders are named at start,
never moved. Not changed: the server's own default state folder on Windows is `%APPDATA%` (roaming) while the Windows
shell uses `%LOCALAPPDATA%`; and every server puts a `docs/` folder inside `--dir`, one level more than anybody expects.

### UX-24 · A named style could not be applied to another text box from where people look for it · P1 · fixed 2026-11-12
**Evidence (measured, `e56e8f9`, owner's report).** Restyle a text box, name the new style "Callout", select another
text box: right-click ▸ Style… or Format ▸ Edit this style… opens the style popover, and clicking "Callout" there only
*shows* its look (UX-14, as in composes) — nothing is applied, and a click on B next changes Callout everywhere. The
only working way was Format ▸ Apply style ▸, which nobody found, because composes ("Body text ▾") and computes
("Style ▾") have a picker in their bar and creates had none. **Fix (agreed).** `StylePicker` in creates' insert bar
(`InsertBar.vue` has a slot for it, `SlideWorkspace.vue`): the selected object's main slot (a text box's words, a
shape's outline, a picture's box), and a second picker "Label" for a shape's words (`objectStyleHost(styling,
'label')`). The popover stays preview-only, consistent with the other apps. **Test:** `web/e2e/creates-styles.cjs`
(the reported case, a shape's two pickers, the counts of UX-25).

### UX-25 · All styles… counted uses with the selection's noun · P3 · fixed 2026-11-12
"Body text … 1 shape" (used by a text box) whenever a shape was selected: `StylesDialog` used `host.noun` for every
row. `StyleHost.usesNoun` ("object" for an object host) now names what the counts count.

### UX-26 · The AI mode switch · P2 · fixed 2026-11-12
**Evidence (owner's report, measured).** The segmented control used the page's `--text`, ink, on the always-dark
panel: with *suggest* chosen, "Act at once" was ink on ink in the light theme. And it sat inside the chat section.
**Fix.** Directly above the History & Chat | Help tabs, in the panel's own light inks (unchosen half ≥ 4.5:1, checked
by `demo.cjs`), a real radio group (arrow keys, one tab stop).

### UX-27 · A new object lands exactly on the previous one · P3 · new, open
**Evidence (measured).** Text ▸ Text puts the second text box on the first; the browser scripts move them apart by
dragging. **Fix.** Offset each new object by one grid step (or place it in the first free spot) when another object
sits exactly there.

### UX-28 · The page declares no language · P2 · fixed on `bitv`, awaiting commit
**Evidence (read, 2026-11-13).** No `lang` on `<html>`: `nuxt.config.ts` set none and nothing in `web/app` did, so a screen
reader chose its voice by guesswork, for a UI that is German or English (WCAG 3.1.1, level A). **Fix.** `lang="en"` in the
build, and `useI18n` declares the language once its catalog has loaded (`languageOf`, `setPageLanguage` in
`web/app/lib/i18n.ts`): a German browser whose catalog did not load stays `en`, because that is what is on the screen.
The open dialog and the admin pages are English only; `app.vue` puts `en` back when a document is left. **Test:**
`web/tests/i18n.test.ts`; `web/e2e/regions.cjs` checks `en`, and a `de-DE` browser was checked by hand to give `de`.

### UX-29 · A keyboard user cannot leave the grid · P2 · fixed on `bitv`, awaiting commit
**Evidence (read, 2026-11-13).** `SheetGrid.vue`'s `onKey` takes Tab and Shift+Tab for stepping between cells and
`preventDefault`s them, and nothing else moved focus out (WCAG 2.1.2 no keyboard trap, 2.4.1 bypass blocks). **Fix.** F6 and
Shift+F6 go to the next and previous part of the window (menus, toolbar, document, panel, footer; hidden or empty parts
are skipped; wrapping round), in all three apps, and from the formula bar. `web/app/lib/regions.ts` (`cycleRegions`),
`regionShortcuts` in `shortcuts.ts`, wired once in `DocumentFrame.vue`; parts are marked `data-region`. Listed in
Config ▸ Shortcuts. **Test:** `web/tests/regions.test.ts`, `shortcuts.test.ts`, `web/e2e/regions.cjs` (Chrome only).
**Left.** F6 does not work while a cell is being edited in the grid (the editor keeps its keys: finish with Enter or Esc);
in a browser tab F6 may also be claimed by the browser (Firefox not tried); no menu item carries it.

### UX-30 · The tab title does not name the document · P3 · fixed on `bitv`, awaiting commit
Every tab of one app read "Claudia Computes" (WCAG 2.4.2). `tabTitle(app, documentName)` now gives
"budget 2027 – Claudia Computes". **Test:** `web/tests/shell-bridge.test.ts`, `regions.cjs`.

### PROC-17 · `demo.cjs` fails once the client sends *suggest* · P2 · fixed 2026-11-12
The switch (E7.7) made every client send *suggest* by default; computes cannot propose yet, so `@ai build an example
budget` was refused and the script waited for "Done." in vain. It now chooses "Act at once" first and checks the switch.

### CODE-16 · The macOS client's generated creates menu was stale · P2 · fixed 2026-11-12
`clients/macos/src/generated/menu.creates.json` had no Format ▸ Apply Style… (the Linux manifest has had it); the
Windows job runs `generate_menu.py --all --check`, but no job does that for macOS. Regenerated with this round's menu
changes, and the `windows-client` job now runs the same `--check` for `clients/macos` (Python, no Mac needed).

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

## Not reviewed (and why), round of 2026-11-12

A real language model (no model could be downloaded here; `./start.sh --ai` was run up to loading a stand-in folder,
which OpenVINO GenAI 2026.4 then refused as expected); Windows and macOS clients (nothing runs them here; the Windows
client is reviewed by reading only); the live demo at demo.claudia-office.de (not reachable from here, so SEC-12 there
is likely, not seen); screen readers; Firefox (the browser scripts ran in Chrome for Testing 153).

## Not reviewed (and why), round of 2026-11-05

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
