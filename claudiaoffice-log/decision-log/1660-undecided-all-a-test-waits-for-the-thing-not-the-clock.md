---
id: D1660
title: "A test waits for the thing, not the clock"
status: undecided
applies-to: all
date: 2026-11-25
round: "Test quality (branch test-quality): PROC-66"
supersedes: []
superseded-by: []
---

# D1660 · A test waits for the thing, not the clock

**Proposed 2026-11-25** on `test-quality`; undecided until the owner confirms it.

Coding standards §2 says "no sleeps as synchronisation". This is how a test keeps that:

1. **Work the test must act during is held.** A stand-in for slow work (a model, Anthropic, a directory that hashes, a
   release that packs) waits until the test lets it go: `claudia_ai.testing.Hold` with `hold()`, `begun()` and
   `let_go()`. A check of "the event loop was not blocked" is then made while the work is held: the test's own code ran,
   so the loop ran. No stopwatch.
2. **Background work has an awaitable end**, as a public method of the thing that runs it: `Assistant.idle()`,
   `HostedDocument.rendered()`.
3. **Otherwise a poll with a generous deadline** (ten seconds where the thing takes milliseconds): it returns as soon as
   the condition holds, so a fast machine does not wait for it.
4. **A sleep stays only as** a yield (`sleep(0)`), a poll's pace (inside the loop), a stand-in for slow work that the test
   does not wait for (`# work:` on its line), or a bounded wait for something that must *not* happen (`# must not
   happen:`): that one may miss a bug on a slow machine and never fails a sound build.

`tests/test_no_sleeps_as_waits.py` holds every Python test file and the packages' `testing.py` fakes to rule 4 (a sleep inside any loop passes as a poll's pace; that the loop has a deadline is left to review). TypeScript tests follow the same rules
(`vi.waitFor`, fake timers) without a check yet.

**Notes.** `Hold` lives in `claudia_ai.testing`, not `claudia_core.testing`, because claudia-ai depends on nothing and its
fakes need it; the server's tests import it from there (the server depends on claudia-ai). Rejected: retries of failed
tests (`pytest-rerunfailures`): they hide the bug in the test and a real timing bug of the product alike.
