---
id: D1565
title: "An empty final answer says so, in words that cannot be taken for an answer"
status: current
applies-to: all
date: 2026-11-24
round: "E7.2 Skills and persona per app, with CODE-80 to CODE-82 (branch e7-2-skills-and-persona)"
supersedes: []
superseded-by: []
---

# D1565 · An empty final answer says so, in words that cannot be taken for an answer

**Decided 2026-11-23** (the owner: "Q9 I have nothing to add as an answer is confusing. The ai interface should say 'I could
not comply'"). The second sentence is my reading, listed in the assumptions of the patch.

`ModelEngine._converse` ended a question with `turn.say or "I have nothing to add."`. A model that ran out of room, or whose
only text was a list of requests that did not parse, ended there, and the person read a sentence that sounded like an answer.

At the end of a question, when the model's final answer has no text and no further request:

- it changed nothing: **"I could not comply."**
- it changed something: **"I made these changes: set_cells x2."**

The list "set_cells x2, add_sheet x1" is built by one helper (`_made`), which the sentence "I stopped after N steps … I made these
changes before stopping: …" uses too, so there is one wording. The sentences are English, like the other sentences the AI says
about its own work; when CODE-78 (translated refusals) gives those a catalogue, these two go into it.
