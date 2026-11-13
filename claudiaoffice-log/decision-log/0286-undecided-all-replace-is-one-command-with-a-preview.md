---
id: D286
title: "Replace is one command in the history, and its effect is shown before it is made"
status: undecided
applies-to: all
date: 2026-11-13
round: "Search & replace in all three apps (branch `regex-builder`)"
supersedes: []
superseded-by: []
---

# D286 · Replace is one command in the history, and its effect is shown before it is made

**Replace all is one command**: one line in the history ("Replaced “€” by “EUR” in 2 cells"), one step for Undo (D54), attributed to whoever asked. The command **stores the changes it made** (which cell, what before, what after), not the pattern, so replaying history never depends on the engine; the line names the pattern only for reading. Every match has a **checkbox** to leave it out, and **Replace this one** steps through one by one. **The effect is shown before anything is replaced**: the document shows each changed cell's new text in place, and the list shows before → after. For formulas the later, richer step is the **scratch-copy preview** of D263, which also shows how the cell's value changes. When the AI replaces, it follows the person's act or suggest setting (D262).

**Notes.** Claude's proposal. Rejected: a confirmation dialog for Replace all, since the preview and Undo already answer it and a modal would hide the document the preview is drawn in. In composes a replacement takes on the style of the text it replaces and in creates a text keeps its box and paragraph styles; neither introduces direct formatting (D62, D73).
