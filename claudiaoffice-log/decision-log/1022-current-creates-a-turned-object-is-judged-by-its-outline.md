---
id: D1022
title: "On a slide a turned object is judged by its outline, and a turn that would leave the slide nudges the object back"
status: current
applies-to: creates
date: 2026-11-15
round: "Rotation in the three apps (branch rotation-ui)"
supersedes: []
superseded-by: []
---

# D1022 · On a slide a turned object is judged by its outline, and a turn that would leave the slide nudges the object back

**What has to lie on the 1600 × 900 slide is the turned outline — the bounding box of the frame turned about its centre — not the unturned frame.** A model that checked the frame would refuse a 300 × 100 box turned by 90° at the top edge although it looks perfectly inside the slide, and would accept one whose corner sticks out. Consequently the anchor of a turned object (the unturned frame's top left) may be negative or beyond the slide; exports and print must place it from the anchor and the rotation, not clamp it (D907, D910).

**A turn that would push the outline off the slide moves the object the least that brings it back, in the same step** (owner, 2026-11-15): `nudge_into` in `claudia_core.turning` returns the nearest anchor at which the outline fits, and `turned_anchor` of creates puts it in the command. One undo restores turn and place. If the turned outline cannot fit on the slide at all (a 1500 × 800 box at 45°), the turn is refused with "this object is too large to turn that way: it would be {w} by {h} units on a slide of 1600 by 900". Whole numbers only: `turned_extent` is the ceiling of the outline's width and height, computed from the integer table of sines in millionths that D910 asks for (`SINE_MILLIONTHS`, 0°–90°), never from a floating-point sine.

**Notes.** *Breaking for creates (0.13.0):* `check_anchor` now accepts exactly the anchors `nudge_into` would give, so a log that holds a turned object whose frame, but not whose outline, lay on the slide is refused when replayed. No such object could be made before this change, because nothing turned one by hand yet; the importers write `rotation` for objects from PowerPoint files and are covered by the same check.

**Importers.** *PPTX:* a turned shape that sticks out of the slide is nudged in when it can be, as for a turn by hand; one whose outline can never fit is read upright and counted under the loss code `turn`. *ODP:* a turned element that is not on the slide by its outline is left out, as an upright one that is off the slide always was, and reported as `off-slide-object`. Neither loss code has a message text in the client's loss dialog yet (E10.20).
