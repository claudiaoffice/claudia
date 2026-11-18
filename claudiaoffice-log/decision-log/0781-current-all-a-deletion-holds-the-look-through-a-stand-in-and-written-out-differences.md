---
id: D781
title: "A deletion holds every look: children say what differs from their new parent, what had the style itself goes to a stand-in to be named"
status: current
applies-to: all
date: 2026-11-17
round: "Deleting and hiding styles (E1.10)"
supersedes: []
superseded-by: []
---

# D781 · A deletion holds every look: children say what differs from their new parent, what had the style itself goes to a stand-in to be named

**Children.** Each style based on the deleted one moves to the new parent (the chosen style, for *re-base*; *assign* does not hold looks, D785) and keeps only the properties in which it differs from that parent, computed from what it looked like before (`held_look`). A property the new parent sets and the old look did not gets the value of "nothing" (`INITIAL_CSS`: `font-style: normal`, `margin-left: 0`, …), so the new parent does not show through. The same holds for the three settings a style inherits besides CSS: heading level (`"body"` says "no heading"), numbering (`"none"` says "not numbered") and number format.

**What has the style itself** (a paragraph, an object or its words, a range of cells; each app says which, `restyle_users`) moves to **one stand-in style**: a document style with the deleted style's purpose and look, based on the new parent, kind of the deleted one, named `<name> (kept)` and marked `to_name` until its maker names it (E9.7). There is none when nothing has the style. Deleting a style is thereby "the style was only ever a name for this look, and the name is going": the look stays, the invitation to name it again appears, nothing is lost.

**When a look cannot be held** the deletion is refused with a sentence naming the property, and nothing changes. That is only the case for a property that has no value of "nothing" the same in every app: `font-family`, `font-size`, `color`, `text-align` (by content in a cell, D318), `hyphens`, `vertical-align`, and a shape's `fill`, `stroke` and `stroke-width`. The dialog asks first (`style_deletion`) and disables a target that cannot hold the look, with the reason.

**Notes.** Considered and not chosen: letting a re-base change looks and listing what changes in the dialog (it would amend D226's rule); leaving re-base out of the first round (it would make "re-base" in D226 empty). Taken as the recommended option when the owner chose "Hold the look exactly" on 2026-11-17.
