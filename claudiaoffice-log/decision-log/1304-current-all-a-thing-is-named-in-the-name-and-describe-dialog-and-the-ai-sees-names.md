---
id: D1304
title: "An object is named in the Name & describe dialog, the same in all three apps; the AI sees things by name"
status: current
applies-to: all
date: 2026-11-19
round: "E1 core, closing out the open stories (branch e1-core)"
supersedes: []
superseded-by: []
---

# D1304 · An object is named in the Name & describe dialog, the same in all three apps; the AI sees things by name

**Decided 2026-11-19** by the owner (taking the proposals; E1.13).

**Where an object's name is changed.** In **Name & describe…** (Ctrl+Alt+D, D1225), and nowhere else: no separate name field in the object's properties. The dialog has a **name field** above the description and the *Decorative* switch, in composes, computes and creates, for every kind of object including a table (D1224). It shows a refusal from `RenameThing` in words ("There is already a text called “Intro”"). Sheets, chart tabs and slides keep F2 and double-click on the tab or the slide (E6.24), which are not objects.

**What the AI sees.** The AI's view of a document lists things by name and keeps the id as a hidden reference, so what a person says ("move the logo") and what the AI answers use the same word that a `#` tag does (D551). A name the AI is given is checked against the one namespace like any other.

**Notes.** Found while reading the code for this decision: the dialog behind Name & describe… is `ObjectDescriptionDialog.vue`, titled *Describe object*, and has no name field at all, in any of the three apps (reported to the owner as a bug of size 2, 2026-11-19). The decision is what that dialog must be.
