---
id: D1065
title: "Shapes and text boxes in composes come from the module creates uses"
status: current
applies-to: composes
date: 2026-11-18
round: "The floating object layer in composes (branch floating-objects)"
supersedes: []
superseded-by: []
---

# D1065 · Shapes and text boxes in composes come from the module creates uses

**`claudia_server.shape_methods.add_shape_methods` registers `shapes` and `add_object` for creates and composes alike; only the placement (a point on a slide, a character of a text) and the words a text box is written in differ.** A text box in a text is a block of its own, so its words have a paragraph style of the text (`BOX_WORDS`).

**Notes.** `shapes` now answers `{library, document}` in composes as it does in creates (the earlier composes answer was a plain list: **breaking** for a client that read it; the web's `shapesOf` accepts both). The messages of `add_object` say "here" instead of "on a slide", so the one text serves both apps (the German catalog is updated). Computes does not use shapes and text boxes yet; it needs only a `CellAnchor` placement to take the same module. `set_wrap` is composes only, because only a text has text to wrap.
