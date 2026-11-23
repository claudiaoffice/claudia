---
id: D1432
title: "The web client's three document sessions share the object layer, styles, palette and language, and every change goes through one door that refuses for a viewer before anything is sent"
status: current
applies-to: all
date: 2026-11-21
round: "Architecture improvements and the glossary words in the code (branch architecture-improvements)"
supersedes: []
superseded-by: []
---

# D1432 · One web document session; a viewer is refused before anything is sent

**What all three apps do alike lives once, in `BaseSession`:** inserting a picture or a container, moving, sizing,
turning, removing and describing an object, the styles, the palette and the language, and the reduction of the
events `objects`, `image`, `shape`, `styles` and `palette` into one state shape (`ObjectLayerState`, styles as a
record by id in every app).

**What differs is where an object goes**: a cell anchor (computes), a paragraph and an offset with a size and a wrap
(composes), a frame on a slide (creates). Each app's session turns its place into the wire's terms and hands them to the
shared request (`putPicture`, `addRendering`); selecting the new object is the app's. Moving and sizing take a place, so
they stay each app's own (`moveObject`, `resizeObject`; creates' `move`, `resize`).

**Every change goes through `write()`**, with these exceptions: undo and redo (the server refuses them for a viewer,
and composes waits for typing in its own `undo`/`redo`), redaction and the restore requests (owners and editors only,
asked for in their own dialogs), naming a paragraph when it is pointed at in the chat (a viewer may write in the chat),
and composes' flows that send several requests in one job (`setStyle`, `deviateStyle`, lists, contents), which check
`refused()` and run in one `run()`, because a `write()` inside a `run()` would wait for itself. `write()` refuses for a viewer with "You can only look at this document." before a
request is sent, adds the revision the change is based on, and runs through `run()`, which composes overrides so that
the words still being typed are sent first. Before this, only composes refused at the client; computes sent the change
and showed the server's refusal, creates checked in some places only (CODE-75).

**Why:** the three copies had already drifted (styles as an array in composes, its stacking order not kept, different
read-only checks), against the rule that the clients do not differ in function. Inheritance rather than a separate
object, because the components and the `StyleHost` call these verbs on the session; a separate object would need a
delegate per verb on each session.

**Since E11.7: the policy is in one function.** `BaseSession.call` holds all of it: the refusal for someone who may
only look, the wait in `run()`, the revision a change is based on and the notice when a request fails. `write()` (a
change) and `attempt()` (a request that is not one, no `base`) are its two forms, `changed()` and `asked()` answer
"did it happen?" for the many callers that need no more, and a change that has its own words for one failure says so in
`told` (`deleteStyle`: the refusal that is about that very deletion). So `deleteStyle` goes through `run()` itself, and
composes no longer overrides it. The web tests' fake server holds every request to the server's own description of its
protocol (`docs/web.md`).
