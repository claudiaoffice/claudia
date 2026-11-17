---
id: D727
title: "Owners redact anything, editors their own work"
status: current
applies-to: all
date: 2026-11-17
round: "Who redacts, and the redaction screens, 2026-11-17"
supersedes: [D726]
superseded-by: []
---

# D727 · Owners redact anything, editors their own work

**An owner redacts any step and any chat message she can read; an editor redacts the steps and chat messages she
made herself.** Viewers and the AI do not redact. If an editor's redaction would blank a later step by somebody else
(D722), it is refused with their names, for an owner to do: nobody's work is blanked by someone who could not have
changed it otherwise. Everything else of D726 stays: a redaction is asked for as a plan (`redaction_plan`, nothing
changes) and confirmed by repeating the dependents that were shown (`redact`); nobody redacts while a suggestion to
restore is open; everybody connected gets `redacted` (and `rebuilt`).

**Notes.** The owner's choice of 2026-11-17, replacing "owners only". It matches what an editor can already do to her
own work (undo, delete) and lets a person take back what she pasted by mistake without asking anybody. The record of the
redaction stays, with who, when and how many, so the act is never hidden; what is lost is the content, which is the
point. Steps the AI made at an editor's request are authored by `ai`, not by her, so only an owner redacts them; the
log does not record who asked (a later decision could add that). A document that has to keep everything its editors
wrote (records retention, say in public administration) may later want a switch "only owners redact"; not built.
