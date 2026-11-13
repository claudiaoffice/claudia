---
id: D265
title: "Creates gets an AI that can act, directly"
status: current
applies-to: creates
date: 2026-11-11
round: "The AI agent: rights, modes and proposals (E7)"
supersedes: [D85]
superseded-by: []
---

# D265 · Creates gets an AI that can act, directly

**Creates gets an AI participant that can write, from the first version, with the same modes as the other apps (D262) and no read-only stage in between.** It is model-driven like computes. Its writes are the object and slide methods that need no binary data: adding a slide, adding a text box or a shape, setting text and paragraph style, moving, resizing and removing objects. Not images, export, snapping or rotation to begin with. While it works on an object it holds it like a person does (E10.6) and releases it afterwards.

**Notes.** Supersedes D85 ("No AI participant for creates yet"). Default mode is suggest (D262), so the first release of the creates AI needs proposals (D263), which for slides show as ghost objects. A scripted stand-in for creates ("add slide Agenda") is *not* part of this: it would only make the demo server answer like the other two apps, and is a small separate story if wanted. Without a configured model, `@ai` in creates says so instead of "ai is not here". **Not solved:** the AI cannot tell from slide data alone that text overflows its box (E10.13 lists clipping as open), and a vision-capable model would need a rendering (E10.9, E7.5).
