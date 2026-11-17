---
id: D720
title: "A redacted step keeps its shape and loses its content"
status: current
applies-to: all
date: 2026-11-16
round: "The redaction contract (D229), 2026-11-16"
supersedes: [D229]
superseded-by: []
---

# D720 · A redacted step keeps its shape and loses its content

**A redacted step keeps its shape and loses its content.** Its revision, author, time, kind and place in the order
stay, and so does its shape: the ids of what it makes, the places and lengths it touches. Everything a person wrote,
typed, picked or imported goes: typed text becomes `█` filler of the same length, cells are emptied, a picture keeps its
id and pixel size but shows one grey pixel, an object loses its words, its description and the alternative text, name
and path of its import record, a chart keeps what it reads but loses its titles. A command that has nothing later steps
depend on becomes a content-free tombstone. The redaction itself is a step in the history (`core.Redaction`), naming
the steps and chat messages it blanked, never what they held.

**Notes.** Option A of the three put to the owner (same shape / cut out and shift later steps / squash the history up to
the step); the owner agreed on 2026-11-16. It was what the apps already did, and it fits models that name things by id.
Accepted cost: the shape can say something (a value of 12 characters sat in B3). The help text says so. Cutting a step
out (B) would drop later edits of the same content and fail where `shifted_by` cannot follow; squashing (C) would lose
who did what before the step. The kernel contract is `Command.redacted()` / `redacted_in(model)`.
