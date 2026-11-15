---
id: D553
title: "A replay can mark what changed since, centres what it follows, and a step can be restored"
status: current
applies-to: all
date: 2026-11-15
round: "The dock: names, scrubbing and tags (branch dock)"
supersedes: []
superseded-by: []
---

# D553 · Replay: marks, differences from now, and restoring a step

**Marks.** While a step is on show, the places it changed are marked in the view: cells, floating objects, paragraphs.
The mark is a solid outline (with a light tint); it is never only a colour. Slides and sheets mark the objects by id, the
sheet marks cell ranges, the text view marks the whole paragraph.

**Show differences from now.** A switch in the replay bar. When on, every place that changed *after* the step on show is
marked as well, with a dashed outline and a hatch, and the bar says in words how many places that is ("Places that
differ from now: 12", or "More than 500 places differ from now"). The server answers it with `changes_since(revision)`:
one forward replay of the line from that step on a scratch model, each step's own places read against the state after
it, together with its inverse's so that what was taken away is named where it was. At most 500 places are listed.

**Centring.** A change a replay follows that is out of sight in the grid is brought to the middle of it; one in sight is
left where it is. (D551 had said this; the grid used to move only as far as the edge.)

**Restoring a step.** "↺ restore this step" in the replay bar suggests going back to the document as it was after the
step on show. It is the checkpoint restore of E3.7 for any step: the same agreement (everybody connected as owner or
editor, at once if one is alone), the same fork: the document continues on a new line `restore-N`, what came after stays
on the old one, nothing is lost. `propose_restore_step` and `Document.restore_revision`; the assistant may not suggest
it. Only a step of the line the document is on; a side line's steps are reached by switching to it.

**While replaying.** A suggestion changes nothing until it is agreed, so `propose_restore_step`, `answer_restore` and
`withdraw_restore` may be asked from the past; so may `changes_since`.

**Composes.** Tags to floating objects show the name the object has now: the session remembers the names it last read.
Reference in Chat stays off in composes, because floating objects cannot be selected in the editor yet.
