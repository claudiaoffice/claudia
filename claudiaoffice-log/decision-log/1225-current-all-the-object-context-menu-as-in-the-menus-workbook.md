---
id: D1225
title: "The object context menu is one list for all three apps, as the menus workbook v4 sets it"
status: current
applies-to: all
date: 2026-11-18
round: "Object interaction in the three apps (branch object-interaction)"
supersedes: []
superseded-by: []
---

# D1225 · The object context menu is one list for all three apps, as the menus workbook v4 sets it

**Right press on an object offers, in this order:** *Name & describe…* (Ctrl+Alt+D) · *Edit text* (Enter; not for a picture or a chart) · *Style…* (Ctrl+Alt+A; for a picture it also holds what "Properties" did) · *Rotate by…* (Ctrl+Shift+Alt+Z) · *Wrap text…* (composes only) · — · *Cut* and *Copy* (pictures only) · — · *Release from grid* (creates only; the one entry that swaps with "Snap to grid") · *Delete* (Del). There are no 90° entries; they are done in Rotate by…. **Rotate by… is not offered for a chart (D1021) or a table.** Edit text is in all three apps: Enter, F2 and the entry edit the words of a text box or shape wherever it floats.

**Wrap text…** is a submenu of the four modes of D1061 with a checkmark on the current one (Over the text, Around the object, Above and below the object, Behind the text) and *Gap…*; the entry shows Ctrl+Alt+R, which keeps cycling the modes (D1064). It replaces Format ▸ Wrap Text.

The list lives in `object-menu.ts` and is built from the object's kind and the app (a flag for the grid, one for wrap), so the three apps cannot drift apart.

**Notes.** Settled with the owner on 2026-11-18 against `claudia-menus-4.xlsx`: Context menus rows 1–9 and "To decide" #6, #9, #13, #16 (answered here: the workbook guessed "In line with text / No wrap", the repo has the four modes). It supersedes the earlier proposal of this branch (Rotate Right 90°, Rotate Left 90°, no Snap to grid in composes and computes), which is no longer in the note. Keys of context-only entries (Release from grid, Wrap text…'s submenu items) follow "To decide" #20.
