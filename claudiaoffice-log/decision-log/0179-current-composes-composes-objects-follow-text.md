---
id: D179
title: "A composes object hangs from a paragraph and follows the text, where a computes object's anchor is deliberately frozen"
status: current
applies-to: composes
date: 2026-11-08
round: "Shapes, images and styles: one shared object layer (thirty-first round)"
supersedes: []
superseded-by: []
---

# D179 · A composes object hangs from a paragraph and follows the text, where a computes object's anchor is deliberately frozen

**A composes object hangs from a paragraph and *follows* the text, where a computes object's anchor is deliberately frozen.** `BlockAnchor(block, offset)`: the paragraph and the character in it the object hangs from. It floats over the text — the words around it do not wrap beside it and are not pushed down by it, text wrap being a layout feature of its own and not in this round. But the anchor does move through other people's edits, by the same `TextCommand.follow` that cursors, zones and suggestions already use (`claudia_composes.spans`), because a character offset is meaningless once the text under it shifts: it would point at a different word. A paragraph joined into the one before it carries its objects with it (`TextModel.carry_objects`); a split hands the objects past the cut to the new paragraph. This is the clearest illustration of why the anchor is the per-app part: the same picture wants frozen coordinates on a sheet, where a row insert must not make it leap, and following ones in a paragraph.

**Notes.** Settled by `AskUserQuestion` against a block-level anchor (the object owning a paragraph slot in the flow, with text above and below but never beside) and against leaving composes out of this round; the owner took the recommended floating, no-reflow first step. composes previously had no object layer at all, so this is new state: `images`, `shapes`, `objects` in `serialize`, and `plain-shape`/`plain-image` added to its built-in styles under the same ids the other two apps use, so an object carried between apps keeps a style that exists where it lands.
