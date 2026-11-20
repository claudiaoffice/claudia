---
id: D1332
title: "A new picture or container is at least as tall as the letters of the body text"
status: current
applies-to: all
date: 2026-11-20
round: "Bug fixes: tables and object sizes (branch fix-table-exit-object-sizes)"
supersedes: []
superseded-by: []
---

# D1332 · A new picture or container is at least as tall as the letters of the body text

**Decided 2026-11-20** (the owner accepted the proposals made after a first LaTeX formula came out tiny in composes).
This adds a least size to the most of D1229.

**What happened.** XeLaTeX draws `E = mc^2` as a picture of 43 × 12. The first picture was fitted with the 20 units
every object has at least, *per side*: the frame became 43 × 20 and the formula sat in it, letterboxed, 12 high, smaller
than the 16 px letters of the body text around it, and the type label ("LaTeX", in the corner) covered most of it.

**A new picture or container is at least as tall as the font size of the document's body text**, with its proportions
kept: a short formula is scaled up until it is as tall as the body text's letters are. The font size is that of the
body text style of the document as it is now (composes "Body text", 12 pt; computes "Body text", 13 px; creates "Body
text", 40 units of the 1600-wide slide), in the app's own units, so the rule means the same in all three apps. It is
never less than the 20 units every object has at least, and **every raise keeps the proportions**: the formula above
becomes 72 × 20, not 43 × 20. In composes and computes the body text is smaller than 20 units, so there the 20 decide.

**The type label** of a container ("LaTeX", "Mermaid", "Typst" in its corner) is drawn while the container has no
picture (empty, drawing, failed) and, once it has one, only while the pointer is over it, so that it never covers a
small picture. It stays text, never colour alone (BITV), and is not read by a screen reader (the description is).

- **The least wins over the most** (420 × 240): a long one-line formula is as tall as the body text and as wide as that
  makes it. It is never wider than the room it has: the text column of the page in composes, what is left of the slide
  to the right of where it starts in creates; a sheet sets no such limit.
- **Pictures and containers**, the two kinds whose size comes from what they show. A text box and a shape have
  default sizes well above the least.
- **Only new ones, once:** a container's first picture (D1229), and a picture when it comes in from a file. A size the
  person sets with the handles is kept, and may go down to the 20 units of every object. A picture pasted from the
  object clipboard keeps the size it was copied at.

**Where.** The server applies it (`claudia_core.new_object_size`), so that whatever adds the object (the clients, the
`ai` user, a later import path) gets the same size: `add_rendering` with `fit` for the first picture of a container,
and `add_image` with `fit` (new) for a picture from a file. The model says how tall its body text is
(`ObjectModel.least_new_size`) and how much room a new object has (`ObjectModel.room_for_new_object`).

**Notes.** An alternative for LaTeX and Typst only was to scale the formula so that its letters are exactly the size
of the body text's; the least height is simpler, holds for Mermaid and pictures too, and comes close for a formula of
one line.
