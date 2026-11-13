---
id: D144
title: "Leaving a document is a new primitive, separate from removing someone else"
status: current
applies-to: all
date: 2026-11-06
round: "The Manage menu: leaving, handing over ownership, exporting and deleting (twenty-third round)"
supersedes: []
superseded-by: []
---

# D144 · Leaving a document is a new primitive, separate from removing someone else

**Leaving a document is a new primitive, separate from removing someone else.** `leave_document()` needs none of the three domain keys — a viewer holding only the content key can still remove their own slot — while `remove_user()` still requires all three. The only invariant anywhere is "at least one owner remains," never "exactly one": `add_user(..., Role.OWNER)` already adds a second owner with no special ceremony.

**Notes.** Corrects an earlier working assumption that the container only ever allowed a single owner; it does not, and nothing new had to be built to allow a second one — only to let someone leave without holding every key.
