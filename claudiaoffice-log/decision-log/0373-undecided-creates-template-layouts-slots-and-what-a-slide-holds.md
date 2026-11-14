---
id: D373
title: "A template holds page format, palette, fonts, styles, layouts and running items; a layout is named slots; a slide is its layout, slot contents and free objects"
status: undecided
applies-to: creates
date: 2026-11-13
round: "Real-world documents: templates and layouts in creates (branch real-world-docs)"
supersedes: []
superseded-by: []
---

# D373 · A template holds page format, palette, fonts, styles, layouts and running items; a layout is named slots; a slide is its layout, slot contents and free objects

**Proposal.** A *template* is what slides share and no slide can change: page format, palette (D200), fonts, the
named styles (D300–D318), its *layouts* and its *running items* (footer text, slide number, date, and the layouts that
do not show them). A *layout* is a named set of *slots* and which running items it shows; a *named variant* is a layout
with a base and one named difference. A *slot* has a kind (`title`, `text`, `picture`; later `chart`, `table`,
`formula`), a name, a frame on the 50-unit grid (E10.15), the style its words take and the style its box takes (D304),
and a hint for when it is empty; a layout has at most one `title` slot. A *slide* is the name of its layout, the
content of each slot (ordinary objects of the shared object layer, D177, that say which slot they are in) and free
objects. **Only place and size of slot content may differ from the slot**; a different look is a named style (D75,
D306). A slide that differs is listed, never refused. Notes are not a slot. Every change is one command with its
inverse.

Changing a slide's layout gives each slot the content of the same kind, in order; content without a slot of its kind
becomes a free object where it was, and the command says how many. Free objects never move.

**Notes.** Screens: `claudiaoffice-log/notes/mockups/creates-templates-slide.svg`, `creates-templates-editor.svg`,
`creates-templates-import-and-new.svg`; reasoning in `claudiaoffice-log/notes/e10-4-templates-layouts-slots.md`.
Answers D68 ("never unsure where a slide comes from") and fills in E10.4 and E10.5.
