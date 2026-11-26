# Implementation note: bug eater, batch 6

Written 2026-11-26, branch `batch-6` (from `main` at `9380988d`, which holds `batch-5` and `backlog`). The brief is
`notes/bug-eater.md`; the batch comes from the triage of 2026-11-26 and the owner's three asks of the same day:
take `apply` away and test at the seams clients use, check whether `base` can be mandatory, and whether the places
that add it can be fewer. Only the first is built; the other two are answered below as a proposal.

## What changed

| Item | Change | Test written first (seen red) |
|---|---|---|
| SEC-25, SEC-30 (D2010) | The protocol's `apply` is gone: no method takes a change in its stored form `{k, s, d}`. A person's change, and the ai's, comes in only through an app's named methods and their checks. `CommandRegistry.for_persons()` and `ServerOnly` (D2007, never released) had no other caller and are gone; `Command.sender` and `tests/command_senders.json` stay. The refusals' messages left the catalogs | `test_no_method_takes_a_change_in_its_stored_form` (core, composes, computes, creates tables): red while `apply` was there |
| Tests at the seam clients use | `packages/claudia-server/tests/list_app.py`: the test app `ListModel` gets a method table of its own (`insert`, `remove`), given to the `Hub` the way the apps give theirs; the redaction tests' naive list passes its own changes. The tests of the hub, locks, stale edits, audiences, restore, redaction, listing and sealed files write through it (about 100 calls in 15 files) | each converted file was run before and after; the protocol tests were converted first (red: `list_app` missing) |

Tests that were about `apply` itself are gone with it: decoding (unknown kind, too new, broken shape), the eight
server-only kinds alone and in a batch, a batch of a person's own changes, the assistant's raw command (SEC-10 item 3),
and a raw `ApplyCalculated` (computes). Their risk now has no way in; the rule is held by the test above.

**Owner's choice** (2026-11-26, asked before converting): the test app's own methods rather than rewriting these tests
on composes.

**Versions:** claudia-server's changelog has an *Unreleased* section, **Breaking**: `apply` removed. claudia-core's
*Unreleased* entry of D2007 now says `for_persons()` and `ServerOnly` are gone again before a release. API snapshot
regenerated (two names fewer in claudia_core).

## Making `base` mandatory, and adding it in one place (proposal, not built)

**Where it stands (measured on `c800a884`).** 117 write methods; 99 take `base`, all as `base:revision?`, so a request
without it is accepted and `Document.execute(base=None)` skips the stale check. The 18 without it: `undo`, `redo`,
`save_checkpoint`, `chat`, `lock`, `unlock`, `hold`, `redact`, `set_ai_consent`, the restore and switch consent flow
(`propose_restore`, `propose_restore_step`, `propose_switch`, `answer_restore`, `withdraw_restore`,
`set_restore_policy`, `discard_side_history`), `what_if_apply`, `what_if_commit`.

Who calls the 99 without `base` today:
- **web client:** nobody. 78 calls go through `write()`, which adds it; 13 add it by hand: the 12 composes calls that
  run inside a queued job (`replace_text` twice, `set_style`, `name_thing`, `insert_reference`, `insert_contents`,
  `remove_contents`, `make_list` and `indent_item` twice each, `deviate_style`) and `delete_style` in all apps
  (`base-session.ts`, through `request()`). The GTK and Neutralino shells send no
  document methods of their own.
- **the ai:** never (`model_engine.HIDDEN_PARAMS` hides it from the model; `Assistant._call` adds none).
- **`what_if_apply`:** whatever its inner `params` hold.
- about 970 calls in 54 server test files (counted by method name; `scripts/measure_blocks.py` calls
  `Document.execute` directly, not a method).

**Can it be mandatory? Yes**, with one rule for `null`: the web client sends `base: null` for a document that has no
step yet (a composes text whose maker's language is unknown starts empty), so "mandatory" means *present*, and `null`
is accepted only while the document has no revision; otherwise it is `stale`. The ai sends the revision its plan was
made on (`on_path` asks only whether that revision is still on the line, so its later steps keep passing).

**Proposal: base belongs to the request, not to 99 methods.**
1. Server: `MethodTable.dispatch` reads `base` once for every write method and checks it before the handler runs, the
   same check `execute` makes (`log.on_path`), so `stale` is decided in one place. The handlers lose their `base`
   parameter and the ~180 `base=base` hand-overs; `Document.execute(base=...)` stays for the server's own callers.
   Exempt, by a flag on the method: presence and chat (`lock`, `unlock`, `hold`, `chat`, `set_ai_consent`) and the
   consent flow, which names its own revisions. `undo`, `redo` and `save_checkpoint` get the check too (see SEC-32).
2. Wire: `base` moves out of `params` into the request frame, `{id, method, params, base}` (protocol 2 → 3).
3. Web: `Link.request` (or `attempt`) puts `base: state.revision` on every request; the 12 hand-added ones and
   `write()`'s go (14 places today). Reads ignore it. The client then has one place where `base` is added, the server
   one where it is checked.
4. The ai: `Assistant._call` passes the revision its task was planned on. `what_if_apply` checks the frame's `base`.
5. Tests: the server tests' request helpers (about 15: `call`, `Client`, `Peer`, `Person`, ...) add `base` the way the
   client does, so the 970 calls do not change.

The smaller step, if the owner prefers it: keep `base` a parameter, make it required (`base:revision` with `null`
allowed only on an empty document), and teach the ai and the test helpers to send it. That closes SEC-32 but keeps the
99 specs and the 14 places in the client.

**The code review** (two reviewers, standards and spec) found: `docs/server.md` still described `apply`;
`PROTOCOL_VERSION` not raised (now 3; `docs/core-kernel.md` said 1); D2007's rule still spoke of `for_persons()` in the
present; `list_app.py` rebuilt `wire.done` and had no types; a stale `used._apply` in `vulture_whitelist.py`;
`web/public/i18n/xx.json` not regenerated; the note's count of places that add `base` missed `delete_style` and
wrongly named `scripts/measure_blocks.py`. All fixed. Not changed: `test_no_method_takes_a_change_in_its_stored_form`
finds a raw-change method by its name and a parameter named `command`, so a method taking `change: dict` would pass
it; no method can be checked for what it decodes. `Command.sender` is read by nothing at run time (question to the
owner, below).

## Assumptions

- `Command.sender` and `tests/command_senders.json` stay: nothing enforces them now, but they say which kinds only the
  server makes, which the next way in for a change from outside (offline merge, a remote engine) will need. To be
  confirmed by the owner (question in the report); if not wanted, both go.
- SEC-30's person path is closed with `apply`; an asset read from a document file or an import still skips the SVG
  sanitising, so SEC-30 stays open, narrowed.

## Found in this batch (proposed, not yet logged)

| ID | Size | What | How known |
|---|---|---|---|
| SEC-32 | 3 | A change sent without `base` skips the stale check: `base` is optional on all 99 methods that take it, and the ai never sends one. `save_checkpoint`, `undo` and `redo` take none at all, so a checkpoint can be put on a line its maker has not seen (after a restore, before her client reloads) | measured (the table) / read |

## Say what could not be run

- Firefox: Playwright's Firefox is not installed in this workspace; the journeys ran in Chromium only.
- The GTK tests that need a display.
