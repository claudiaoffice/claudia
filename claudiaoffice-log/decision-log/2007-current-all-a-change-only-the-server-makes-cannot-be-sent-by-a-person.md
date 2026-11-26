---
id: D2007
title: "A change only the server makes cannot be sent by a person: every kind of change says who may send it"
status: current
applies-to: all
date: 2026-11-25
round: "Bug eater, batch 5 (branch batch-5): SEC-25"
supersedes: []
superseded-by: []
---

# D2007 · A change only the server makes cannot be sent by a person: every kind of change says who may send it

**Decided 2026-11-25** by the owner (architecture review of 2026-11-25, candidate "who may send a command").

The protocol's `apply` runs a change in its stored form `{k, s, d}`. It was meant for the changes the apps make, but it
decoded every kind the server knows, so an editor could send what only the server makes, through its own methods and
their checks: she could replace the document with a `core.Import` (no undo), and write a checkpoint ("Approved by
legal"), a redaction record or a restore record that never went through who-may-do-this (D51, D727), also hidden inside
a `Batch`. The apps never send raw changes; only the tests and scripts do.

**Rule.** Every kind of change says who may send it (`Command.sender`): `"person"`, the default, or `"server"`. Server
only are `core.Import`, `core.Setup`, `core.Checkpoint`, `core.Redaction`, `core.Redacted`, `core.Restore` and
`core.Switch`: each is made by the server's own method (import, a new document, File ▸ Save, Redact…, Restore…, the
switch of line), which checks the role first. So is `computes.ApplyCalculated`, a heavy formula's result, which only
the server's worker lands (found by the review of the list; written as the assistant's, it would let a person put any
value on a waiting cell under that name). `apply` decodes what a person sends with the registry
`for_persons()`, which refuses a server-only kind with `ServerOnly` (`forbidden` on the wire) wherever it sits: a
change that holds changes decodes them through the same registry, so a batch cannot carry one in. Nothing changes and
nothing is written to the history.

**Review.** `packages/claudia-server/tests/command_senders.json` lists every kind of every app with who may send it; a
new kind fails a test until somebody says which it is, the way `method_reads.json` does for what a method reads (D1261).

**Notes.** `apply` stayed at first, as the protocol's general way to edit; D2010 (2026-11-26) took it away, and with it `for_persons()` and `ServerOnly`. `Command.sender` and the list stay. The assistant may not
use it at all (SEC-10). Not decided here: whether a person's raw `core.DefineAsset` should pass the checks `add_image`
makes (an SVG is sanitised there, not when an asset is read back).
