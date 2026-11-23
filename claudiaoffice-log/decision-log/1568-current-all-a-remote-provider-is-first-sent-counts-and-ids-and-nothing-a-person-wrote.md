---
id: D1568
title: "A remote provider is first sent counts and ids, and nothing a person wrote"
status: current
applies-to: all
date: 2026-11-23
round: "E7.2 Skills and persona per app, with CODE-80 to CODE-82 (branch e7-2-skills-and-persona)"
supersedes: []
superseded-by: []
---

# D1568 · A remote provider is first sent counts and ids, and nothing a person wrote

**Decided 2026-11-23** (the owner: "please fix CODE-80 in this work"; CODE-80 was found in the code review of E7.11).

The first message of a question describes the document so that the model need not ask for everything. For the local model
that stays on the server and is unchanged. For a remote provider (Claude) it is content that leaves the server before the
model has asked for anything, so it holds **counts and ids and nothing a person wrote**: how many sheets (and their ids),
how many paragraphs, headings and tables (and the id of the paragraph the asker is in), how many slides and objects on each.
No sheet name, no cell, no heading, no style name, no word of a paragraph or of a slide. The model is told to look at what the
question is about, with its own requests, and only at that; what it looked at is what goes out, which is what the dialog of
the owners' consent says ("Claude reads what it is shown").

The lens decides what is shown (`orient(..., remote=True)`); the router says whether the answer is remote (`Via.remote`), so
the lens never learns which provider it is.

**Costs and what stays.** One more round for most questions to a remote provider (the look), within the rounds a question may
use. What a model *looks at* is sent in full, as before, and so is the earlier chat of the same person (D1498: the memory
goes with the question whoever answered it), which can hold what an earlier answer of the local model quoted: that is said in
the implementation note and is not changed here. The asker's own account name is still part of "where her cursor is".
