---
id: D1663
title: "A \"must not break\" test is marked with its story, and every story that is done has one"
status: undecided
applies-to: all
date: 2026-11-25
round: "Test quality (branch test-quality): PROC-68"
supersedes: []
superseded-by: []
---

# D1663 · A "must not break" test is marked with its story, and every story that is done has one

**Proposed 2026-11-25** on `test-quality`; undecided until the owner confirms it.

Coding standards §2 says every feature has at least one test of its key risk, marked "must not break". The mark names
the story, in the form of the place the test lives:

* a unit or API test: `@pytest.mark.must_not_break("E7.11")` (registered in `pyproject.toml`);
* a scenario: the tag `@must-not-break:E7.11`;
* a vitest test: `[must not break: E7.11]` in its title.

`tests/test_must_not_break.py` checks that every mark names a story of the backlog, and that every story that is done
has a mark. The 46 stories done before the rule stand in its `NOT_MARKED_YET`; the list only shrinks, and a story done
from now on comes with its mark. Which test covers a story's key risk is the owner's call; the first mark (E7.11:
nothing of a document reaches Anthropic without the owners' consent) is a proposal.

**Notes.** Rejected: a marker without a story (nothing to check it against), and a list of marked tests kept beside the
code (it drifts).
