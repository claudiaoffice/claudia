---
id: D1105
title: "A corkboard card is a view of the document's structure, with a status and one free note"
status: current
applies-to: all
date: 2026-11-18
round: "Workflow: focus, corkboard, scrapbook and the private drawer (first round)"
supersedes: []
superseded-by: []
---

# D1105 · A corkboard card is a view of the document's structure, with a status and one free note

**View ▸ Corkboard arranges the parts of the document as cards. A card's title is read from the document and cannot be edited on the card; the person edits only its status and one free-text note.** The note is not structured: when it is empty it shows grey text priming its use ("put your goals, summary or other notes here…"). The status is a chip with an icon and a word, never colour alone. Dragging a card is the same logged command as moving the section in the document (`move_section`, with renumbering), so the corkboard and the text cannot disagree. A card may also be empty (a planned part that has no text yet).

**Notes.** Status and note are stored in the document as logged commands in the content key domain, like any other content. An open point (D1109) shows as a badge on the card. The corkboard also gives the overview and the progress picture that the heatmap was meant for (D1116).
