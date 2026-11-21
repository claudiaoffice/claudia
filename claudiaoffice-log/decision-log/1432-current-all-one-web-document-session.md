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

**What differs is where an object goes**, the session's place type: a cell anchor (computes), a paragraph and an
offset with a size and a wrap (composes), a frame on a slide (creates). Each app's session turns its place into the
wire's terms (`placeOnWire`) and may select a new object (`afterAdd`).

**Every change goes through `write()`.** It refuses for a viewer with "You can only look at this document." before a
request is sent, adds the revision the change is based on, and runs through `run()`, which composes overrides so that
the words still being typed are sent first. Before this, only composes refused at the client; computes sent the change
and showed the server's refusal, creates checked in some places only (CODE-75).

**Why:** the three copies had already drifted (styles as an array in composes, its stacking order not kept, different
read-only checks), against the rule that the clients do not differ in function. Inheritance rather than a separate
object, because the components and the `StyleHost` call these verbs on the session; a separate object would need a
delegate per verb on each session.
