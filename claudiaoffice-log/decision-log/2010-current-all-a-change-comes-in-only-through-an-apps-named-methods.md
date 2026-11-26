---
id: D2010
title: "A change comes in only through an app's named methods: the protocol's apply is gone"
status: current
applies-to: all
date: 2026-11-26
round: "Bug eater, batch 6 (branch batch-6): SEC-25, SEC-30"
supersedes: []
superseded-by: []
---

# D2010 · A change comes in only through an app's named methods: the protocol's `apply` is gone

**Decided 2026-11-26** by the owner (bug eater, triage of 2026-11-26: "remove apply() entirely … testing should be at
seams that are actually used").

**Rule.** No method takes a change in its stored form `{k, s, d}`. A person's change, and the ai's, comes in only through
an app's named methods (`set_cells`, `replace_text`, `add_object`, `undo`, …), which build the change and make their
checks first. The stored form travels only from the server to clients: in events and in `changes_since`.

**Why.** `apply` ran whatever change the registry knew, as the person who sent it. Every check an app's method makes
before it builds a change (a place that is there, a picture that is decoded and sanitised, who may set up the page, who
may restore or redact) was one `apply` away from being skipped. D2007 closed the worst of it for the eight kinds only the
server makes; SEC-30 showed that the others are open too (a raw `core.DefineAsset` skips the SVG sanitising of
`add_image`). No client, and not the ai (SEC-10), sent `apply`: only the server's tests did. Taking it away closes the
whole class at once instead of one kind at a time.

**Tests.** They write at the seam clients use. The server's tests of the hub, locks, stale edits, audiences, restore,
redaction and sealed files use the test app (`ListModel`) through a method table of its own,
`packages/claudia-server/tests/list_app.py` (`insert`, `remove`), given to the `Hub` the way composes, computes and
creates give theirs. `test_no_method_takes_a_change_in_its_stored_form` checks the core table and the three apps' tables.

**Consequences.** `CommandRegistry.for_persons()` and the `ServerOnly` error (D2007) had no other caller and are gone
(never released). `Command.sender` and `tests/command_senders.json` stay for now: they say which kinds only the server
makes. Supersedes the note of D2007 that `apply` stays.
