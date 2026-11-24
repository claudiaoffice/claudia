---
id: D1541
title: "A key typed in a field or in a dialog belongs to it, not to the object behind it"
status: current
applies-to: creates
date: 2026-11-24
round: "E10.4 Templates, layouts and placeholders (branch e10-4-templates-and-layouts), UX-78"
supersedes: []
superseded-by: []
---

# D1541 · Whose a key is

The slide takes Delete, Backspace and the arrow keys for the selected object. A dialog is drawn inside the slide's
element, so what is typed in it reaches the slide as well. The slide let a key through only when it came from an
element with `role="dialog"`, which a native `<dialog>` does not have. In Name & describe… the arrow keys moved the
text box behind the dialog and Backspace deleted it, with the dialog still open on a thing that was gone (UX-78).

A key pressed in a field that is typed into, or anywhere inside a `<dialog>` or an element with `role="dialog"`, is for
that field or dialog and for nothing behind it (`lib/key-owner.ts`, `keysAreTheirs`). Only the slide uses it for now:
the grid of computes draws its dialogs outside its keyboard area, so what is typed there does not reach it (checked in
`describe.cjs`).
