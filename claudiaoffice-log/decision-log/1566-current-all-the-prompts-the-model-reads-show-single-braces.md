---
id: D1566
title: "The prompts the model reads show single braces"
status: current
applies-to: all
date: 2026-11-24
round: "E7.2 Skills and persona per app, with CODE-80 to CODE-82 (branch e7-2-skills-and-persona)"
supersedes: []
superseded-by: []
---

# D1566 · The prompts the model reads show single braces

**Decided 2026-11-23** (the owner: Q1 of the E7.2 grilling, fixing CODE-81).

The system message the model got contained doubled braces: `HOW_TO_ASK` was never formatted, so its `{{"method": ...}}` went out as
written, and the examples of the computes and creates lenses are values inserted into a string that is formatted for other keys
(`ORIENTATION.format(example=...)`), so their `{{ }}` stayed doubled. A model copies what it is shown: in composes it did not know
the form of a request and answered with nothing, in creates it pasted its list into the chat.

A text that is *inserted* into a template is plain text and has single braces; only a template that is itself formatted escapes
them. A test reads every request the system message shows, in each of the three apps, as JSON (an example that cannot be read
fails): `tests/test_server_ai_prompt.py`.
