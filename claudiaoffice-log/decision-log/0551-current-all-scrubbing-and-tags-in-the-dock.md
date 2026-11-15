---
id: D551
title: "Scrubbing replays the history from the dock; # in the chat makes a tag that stores an id"
status: current
applies-to: all
date: 2026-11-15
round: "The dock: names, scrubbing and tags (branch dock)"
supersedes: []
superseded-by: []
---

# D551 · Scrubbing replays the history from the dock; # in the chat makes a tag that stores an id

**Scrubbing.** The mouse wheel over the History & Chat panel steps a playhead through the history, and the document view shows the state at that step; Ctrl+wheel scrolls the panel as before. The filter above the history decides which steps the wheel visits. The view follows each step: it stays where it is if the change is in sight, and moves (centred, briefly tinted) to a change that is out of sight. Chat during a replay goes live: a message is posted now, whatever the playhead shows. Keys: Alt+PgUp / Alt+PgDn step, Alt+Home goes to the start, Esc returns to now; View ▸ Replay History… is Ctrl+Alt+Z (Ctrl+Alt+H is History and Chat; Ctrl+Alt+E is AltGr+€ on a German keyboard). Nothing in a replay changes the document: it is a preview, as `peek_line` already is.

**Tags.** Typing `#` in the chat opens a list of the named things in the writer's own view; picking one, or clicking a thing in the view while the box is focused, puts a tag in the message. A `#1` that is not picked stays plain text. The tag stores the **id** and shows the **current name**, so a rename never breaks one. Clicking a tag takes any reader to the thing (centred, briefly tinted) with a Back chip; a tag whose thing is gone jumps a replay to the last moment the thing existed. Exports write the name as plain text ("figure 1"). Edit ▸ Reference selection in chat gets a key when it is built (not Ctrl+Alt+R, which is Random Generator; not Ctrl+Alt+T or L, which Ubuntu keeps; not Ctrl+Alt+Q, E, M or a digit, which are AltGr).

**Built so far** (branch `dock`): the names (D550) and the replay (backend, session, panel, menu entry, follow rules). The tags follow, mocked in `notes/mockups/dock-*.svg`.
