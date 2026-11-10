---
id: D155
title: "The AI settings page's \"Apply\" restarts only the AI engine, in the same server process — it does not restart the server"
status: current
applies-to: all
date: 2026-11-07
round: "Server administrators and settings (twenty-seventh round)"
supersedes: []
superseded-by: []
---

# D155 · The AI settings page's "Apply" restarts only the AI engine, in the same server process — it does not restart the server

**The AI settings page's "Apply" restarts only the AI engine, in the same server process — it does not restart the server.** Loads the newly-chosen model, builds its assistant, swaps it in only once the new one is ready, then closes the old engine; already-open documents keep whichever assistant they started with, and the change reaches only documents opened afterward. The whole mechanism is gated off entirely, with no override, when the server was started with `--no-assistant`.

**Notes.** Chosen over restarting the whole server process (the owner's choice between the two, via `AskUserQuestion`): a server can otherwise be mid-session with other documents open, and a settings change should not drop them. The already-open-documents limitation is accepted as a known, documented gap rather than solved by migrating a live document's assistant — `Hub.assistant`/`Hub.max_documents` are read once, at `Hub.open()`.
