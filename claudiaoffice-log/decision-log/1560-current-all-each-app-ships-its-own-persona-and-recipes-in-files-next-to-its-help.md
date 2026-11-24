---
id: D1560
title: "Each app ships its own persona and recipes, in files next to its help"
status: current
applies-to: all
date: 2026-11-24
round: "E7.2 Skills and persona per app, with CODE-80 to CODE-82 (branch e7-2-skills-and-persona)"
supersedes: []
superseded-by: []
---

# D1560 · Each app ships its own persona and recipes, in files next to its help

**Decided 2026-11-23** (Q2–Q4 of the grilling): one branch for the story; a `persona.md` and a `skills.md` for each app;
English only; outside the catalogues; no administrator override yet.

Each of `claudia-computes`, `claudia-composes` and `claudia-creates` has an `ai/` folder with `persona.md` and `skills.md`, next
to its `help/`. They ship with the package the way the help does (the build takes every file under the package). The server
finds them by the package of the document's model class (`claudia_server.ai_guidance.load_guidance`); it knows no recipe itself.
A missing folder gives no guidance and no error, so an app without files still works; a recipe without a `Uses:` line stops the
loading with a message that names the recipe.

The three personas share their first lines word for word (who the ai is, how brief, never inventing, looking in the help first);
each adds a short section about its app after a `## In this app` heading. **A test keeps the shared text identical** so the three
copies cannot drift.

Why English and outside the catalogues: the model reads these files, no person does, and a translation would cost three catalogues
for nothing: the persona tells the model to answer in the language of the person who asked.
