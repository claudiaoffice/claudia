---
id: D1492
title: "When a question to Claude fails nobody else answers: one sentence for the person, the reason for the administrator"
status: current
applies-to: all
date: 2026-11-22
round: "E7.11 Claude as an AI provider (branch e7-11-claude-provider)"
supersedes: []
superseded-by: []
---

# D1492 · When a question to Claude fails nobody else answers: one sentence for the person, the reason for the administrator

**Decided 2026-11-22.**

If Claude fails after the owners allowed it, the person asking reads one sentence whatever the cause:
"Claude is not available at the moment. The administrator can see why." Under it: "Claude · remote · no answer was made".
No other provider answers instead: she would not know who read her document.

The administrator's AI page says the cause (key refused, credit used up, rate limit, overloaded, unreachable, unknown
model, timed out; the last is its own cause) and since when, and says that nothing switches by itself. The last error
stays until Claude has answered a question again. It is kept in memory: a restart forgets it (D1496).
