---
id: D726
title: "Owners redact: plan, look, confirm"
status: superseded
applies-to: all
date: 2026-11-16
round: "The redaction contract (D229), 2026-11-16"
supersedes: [D229]
superseded-by: [D727]
---

# D726 · Owners redact: plan, look, confirm

**Only owners redact, by asking for a plan, looking at it, and confirming it.** The wire has `redaction_plan` (nothing
changes) and `redact` (repeats the dependents it was shown; refused if the plan now names others, and while a restore
suggestion is open). An owner redacts only chat messages she can read; the AI never redacts. Everybody connected gets
`redacted` (and `rebuilt` when steps were blanked).

**Notes.** "As an owner" in E1.8. The screens are proposed as mock-ups in `notes/redaction-ui.md` and are not decided.

*Superseded on 2026-11-17 by D727: editors redact their own work too.*
