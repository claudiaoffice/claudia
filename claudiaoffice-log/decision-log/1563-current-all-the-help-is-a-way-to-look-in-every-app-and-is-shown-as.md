---
id: D1563
title: "The help is a way to look, in every app, and is shown as the product's own words"
status: current
applies-to: all
date: 2026-11-24
round: "E7.2 Skills and persona per app, with CODE-80 to CODE-82 (branch e7-2-skills-and-persona)"
supersedes: []
superseded-by: []
---

# D1563 · The help is a way to look, in every app, and is shown as the product's own words

**Decided 2026-11-23** (Q7); the English reading below is my assumption while building, for the owner's veto.

`help_search` and `help_topic` are in the `look_methods` of all three lenses, so a model, and a person who may only look, can ask
them. The persona tells the model to use them first for any question about how to use Claudia, and to say so if the help has
nothing. `help_search` shows `- id — title` lines; `help_topic` shows the title and the body; the loop cuts a long one like any result (`Budget.result_chars`).

**Their answers are not fenced as data.** Everything that comes out of a document is somebody's text and is fenced; help is the
product's own text, written by us. Fencing it would tell the model to distrust the very thing it was sent to read.

The help is read in English: the assistant's connection has the default language. The model answers in the language of the person
who asked, which the persona demands. Passing the asker's language to the ai's help requests is a possible later step, not done here.
