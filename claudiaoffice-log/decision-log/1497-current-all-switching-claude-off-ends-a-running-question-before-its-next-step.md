---
id: D1497
title: "Switching Claude off, or changing the provider, ends a running question before its next step"
status: current
applies-to: all
date: 2026-11-22
round: "E7.11 Claude as an AI provider (branch e7-11-claude-provider)"
supersedes: []
superseded-by: []
---

# D1497 · Switching Claude off, or changing the provider, ends a running question before its next step

**Decided 2026-11-22.** An owner who withdraws the consent, or an administrator who changes the provider or removes the key
while a question runs, ends that question before its next step with "Stopped: Claude was switched off." (under it:
"Claude · remote · stopped at its next step"). What was already changed stays; it is a step of the history and can be undone as
any step. A switch-off is not a fault of Claude's and does not count as its last error. The next question goes to the server's own provider.

The cause of X1 (an open document kept an assistant whose runner had been closed or replaced) is gone with this: the router
asks the desk per question (CODE-79).
