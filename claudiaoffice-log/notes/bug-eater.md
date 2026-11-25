# The bug eater

A standing agent chat that works down the bug tracker (`bugtracker-open.md`; `bugtracker.md` until 2026-11-25), the architectural problems behind it, and the places where the
code does not yet speak the glossary's language. Agreed with the owner on 2026-11-24. This note is the brief: a new
session starts by reading it, the project instructions, `CONTRIBUTING.md` and `coding-standards.md`, so the owner only
has to say which batch.

## What it works on

| Track | What | How it is decided |
|---|---|---|
| Bugs | The open items of `bugtracker-open.md` | In batches (below); the owner approves the queue |
| Architecture | Root causes that several items share (the execution model, the server's structure, one source for menus …) | Never inside a bugfix: a design pass with class diagrams, a second opinion from Fable, the owner agrees before code |
| Domain language | Glossary words the code does not use yet (Proposal and the other words of "The ai at work") | A domain-modelling session, then one rename across protocol, server, web and clients; no compatibility layer while claudia is pre-release, unless the owner says otherwise |
| Tests | Where the suite is weak: behaviour no test reaches, specs that run nowhere, clients not run | The bug eater points at the weak spot, the owner and the bug eater agree what to do |

## The batch loop

1. **Start.** Merge `backlog` into `main` locally, then make a branch for the batch from it (`batch-1`, `batch-2` …). All
   bug-eater decisions take their numbers from the one block D2001–D2100 (`decision-log/ranges.md`, the owner's rule of
   2026-11-24), in order across batches; a batch does not reserve a block of its own.
2. **Questions first.** Items that need the owner's decision are collected and asked together, each with a proposed
   default the owner only has to veto (`grill-me` where a fix has open questions). Never guess.
3. **Per item.** A test that fails for the right reason, with the one-line reason the bug escaped (spec gap / missing
   test / test passed but wrong; it feeds the invariants list), then the least code that makes it pass, then clean up.
   An item that turns out to be architectural leaves the batch and goes to the architecture track.
4. **End of the batch.** `code-review` over the batch, fix what it finds, run the gate (`check_debt.py`), the E2E
   `@core` specs and "use it before delivery", merge the latest `main` into the branch.
5. **Deliver** patches (never bundles) against the batch's branch, with the done report of the project instructions,
   the decision-log entries, implementation notes, updated specs and what could not be run.
6. **Tracker.** The patch carries a proposal of which items to mark fixed and how the others changed. Items are marked
   fixed only after the owner agrees; then the batch is merged to `main`, CI is checked until green, and the next batch
   starts.

Bugs found along the way are reported with a size (1 huge, 2 medium, 3 small) and the question whether to fix them in
the batch or log them.

## Helpers

- **Sub-agents:** at most two for coding work (each on its own worktree, for well-specified work such as a rename
  sweep, binding a spec's steps or running a client's tests), in addition to the reviewers `code-review` starts.
- **Fable** as advisor for hard questions: a root cause with two plausible explanations, an architecture proposal,
  a security fix. Its answer is reported to the owner as advice, not as a decision.

## How batches are cut

By shared root cause, not one bug at a time, so that related items share their tests and their fix. The current queue
and its clusters are in `bug-eater-queue.md`.
