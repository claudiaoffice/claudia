---
id: D230
title: "The AI's authorisation boundary"
status: current
applies-to: all
date: 2026-11-10
round: "Open design questions"
supersedes: []
superseded-by: []
---

# D230 · The AI's authorisation boundary

**The AI's authorisation boundary:** whether the method allow-list moves from the model's output parser to the server's dispatch, before E7.5 puts document content in the prompt and before D8 makes the engine remote (SEC-10).

*Carried over on 2026-11-10 from the decision log's "Open design questions" section, which had no numbers. Nothing here is decided yet.*

**Checked against the code, 2026-11-17 (`main` at `6814bac`).** Settled by the code: the allow-list is checked at dispatch, not in the model's output parser (SEC-10, fixed 2026-11-06): `MethodTable.dispatch` refuses a write outside `Account.allowed_methods` whatever path reaches it, and `apply` refuses `account.system`. The status is now current, describing that.
