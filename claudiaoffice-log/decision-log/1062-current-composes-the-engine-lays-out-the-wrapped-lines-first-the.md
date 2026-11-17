---
id: D1062
title: "The engine lays out the wrapped lines first; the editor follows in a second stage"
status: current
applies-to: composes
date: 2026-11-17
round: "The floating object layer in composes (branch floating-objects)"
supersedes: []
superseded-by: []
---

# D1062 · The engine lays out the wrapped lines first; the editor follows in a second stage

**Line layout for wrap comes from the layout engine first, for print and the print preview (stage 1). The editor keeps the browser's own lines until a second stage puts a non-editable float of the object's size at the anchor's line.** The owner chose this on 2026-11-17 from three options (print only, the engine for the editor too, engine first and floats later).

**Notes.** Keeps contenteditable (caret, selection, input methods, spell checking, the screen-reader tree for BITV) and keeps the engine as the one place that decides how a document renders. CSS floats wrap on one side only, so a test must compare which lines the float and the engine narrow. Slice 1: `flow/exclusions.ts` and a width per line in `layoutParagraph`.
