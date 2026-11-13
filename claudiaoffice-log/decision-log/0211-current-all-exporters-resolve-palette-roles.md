---
id: D211
title: "An exporter resolves roles against the document's palette, and flattens a translucent one over what it sits on"
status: current
applies-to: all
date: 2026-11-09
round: "The styling dialogs: one menu, three apps (thirty-sixth round)"
supersedes: []
superseded-by: []
---

# D211 · An exporter resolves roles against the document's palette, and flattens a translucent one over what it sits on

**An exporter resolves roles against the document's palette, and flattens a translucent one over what it sits on.** `StyleBook.resolved(style_id, colours)` is the form anything that paints or exports asks for. Where a role carries an opacity and the file format has nowhere to keep one — a solid pptx fill — the colour is composited over the palette's `page` and the flat result is written.

**Notes.** Found by the gate, not by thinking: the pptx exporter read `computed` and looked for a `#rrggbb`, and `@accent/14` holds none, so every shape's fill and border went missing without a word (bugtracker UX-15). Keeping the colour and discarding the 14% was the other option and is worse: a pale wash would export as full-strength iris, a shape that looks nothing like the one on the screen.
