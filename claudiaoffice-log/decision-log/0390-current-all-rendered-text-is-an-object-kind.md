---
id: D390
title: "A rendered text container is an object kind whose text is the truth"
status: current
applies-to: all
date: 2026-11-13
round: "Rendered text containers (branch containers)"
supersedes: []
superseded-by: []
---

# D390 · A rendered text container is an object kind whose text is the truth

**A container of rendered text (a LaTeX formula, a Mermaid diagram, a Typst page) is the object kind `rendered` on the shared object layer (D177). It points at a `RenderedDefinition` the document keeps by id (like a chart's, D179): the text (`source`), what kind of text it is (`type`, a plugin's id the kernel never reads), the person's settings (`params`), the picture last made (`image`) and a note of what made it (`renderer`).** It works in all three apps through the three anchors; only the anchor differs.

**Commands.** `DefineRendering`, `UpdateRendering` and `ForgetRendering` change definitions, the `RenderingsChanged` event tells views. `AddObject` is schema 3 (its upcaster adds the field), and every app's state schema moved up one step to store `renderings`. The kernel stays standard-library only; a purity test keeps it so.

**Notes.** Text is the truth: the picture is a cache that may be missing or old, never the other way round. Rejected: one object kind per tool (every new tool would change the kernel), and a plugin-owned binary format (nothing could open the document without the plugin). Redaction (D21) empties the text and keeps the rest.
