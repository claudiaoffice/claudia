---
id: D395
title: "The picture follows the text as a background job of the hub, and undo follows the person"
status: current
applies-to: all
date: 2026-11-13
round: "Rendered text containers (branch containers)"
supersedes: []
superseded-by: []
---

# D395 · The picture follows the text as a background job of the hub, and undo follows the person

**Wire methods stay synchronous and only change the text. When a definition changes the hub renders it in the background after `RENDER_DELAY` (a burst of typing makes one picture) and takes the picture in as one edit by the person who caused it (`Batch` "Render"). It then sends `render_result` `{id, ok, diagnostics, message, unavailable}`.** A job whose text changed meanwhile drops its result; the frame keeps its width and takes the picture's proportions; the picture it replaces is forgotten if nothing else holds it.

**Notes.** The edit that stores a picture does not start another render (`_made_from` is checked when the event comes and again inside the job). Undo is faithful to history: the render is its own undo step, so after one undo the text can show with the older picture. The submit/status job API of D92 / E3.4 is not built; this path stands in for it. The composes server cannot add an object yet, so its methods are read-only (follow-up).
