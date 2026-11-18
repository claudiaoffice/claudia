---
id: D1068
title: "The flowing editor goes round objects with CSS floats, and says what they cannot do"
status: current
applies-to: composes
date: 2026-11-18
round: "The floating object layer in composes (branch floating-objects)"
supersedes: []
superseded-by: []
---

# D1068 · The flowing editor goes round objects with CSS floats, and says what they cannot do

**Stage 2 of D1062 is built as one invisible, non-editable box (`data-skip`, `contenteditable=false`) at the start of the paragraph an object hangs from, floated to a side, as wide and as high as the room the object takes (*above and below*: the whole width; *around*: from the paragraph's edge to the far side of the object, on the side the object is nearer to), plus the gap.** The box is measured in the order of the text, each with the boxes before it in place and its own out of the lines, so nothing is measured against itself and the same text always gives the same boxes (`web/app/lib/wrap-flow.ts`, pure, tested without a DOM). The printed pages and the print preview stay the engine's (D1062).

**Where an object is.** The place an object hangs at is measured *with its own box out of the lines* and kept from the top left of the text, not from the screen (the page scrolls, and taking the boxes out of the lines can move the view under a measurement: both once drew objects 150 pixels off). Each place is read from one origin at one moment.

**Limits, said and not hidden** (the browser's, not ours):
1. A float takes room from one side of a line. An object in the middle of a column in *around* is gone round on its wider side only; print shows both.
2. A float cannot start above its paragraph, and its top margin is blank room, not room for lines above it. An object anchored *in the middle* of a paragraph therefore pushes the lines before it down too, where print keeps them above the object (reported to the owner as a bug of size 2, to be fixed by putting the box at the anchor's line instead of the paragraph's start).
3. The layer *behind* the words is a second layer under them; with Ctrl held it lies over them so the object can be taken (D1063).

**Tested** in a real Chrome (`web/e2e/composes-wrap.cjs`): a text box in each wrap mode, the key cycling them, an image and a rectangle, scrolling and typing, counting the words that lie over any object (none). Not tested: the two-sided case, which the browser cannot do.
