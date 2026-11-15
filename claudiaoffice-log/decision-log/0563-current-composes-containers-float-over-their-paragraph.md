---
id: D563
title: "In a text a container hangs from a character of a paragraph and floats over it"
status: current
applies-to: composes
date: 2026-11-15
round: "Rendered text containers: the screens (branch containers)"
supersedes: []
superseded-by: []
---

# D563 · In a text a container hangs from a character of a paragraph and floats over it

**Composes places containers with `add_rendering` (`block`, `offset`), moves them with `move_object` (`id`, `block`, `offset`), sizes them with `resize_object` (`id`, `w`, `h`) and removes them with `remove_object`.** The assistant does not write containers in a text, as it does not write the words (D63). On the page the container is drawn in a layer over the text, at the top of its paragraph against the right edge, without pushing any word aside (D179); the arrow keys up and down hang it from the previous or next paragraph, the corner handle sizes it. Floating anywhere on the page by dragging, and text wrap, are follow-ups.
