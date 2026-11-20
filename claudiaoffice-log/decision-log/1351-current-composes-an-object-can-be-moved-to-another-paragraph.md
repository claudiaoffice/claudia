---
id: D1351
title: "An object in a text can be moved to another paragraph"
status: current
applies-to: composes
date: 2026-11-20
round: "Bug fixes: stale tests, the caret, dragging objects (branch fix-stale-tests-caret-drag)"
supersedes: []
superseded-by: []
---

# D1351 · An object in a text can be moved to another paragraph

**Decided 2026-11-20** (the owner accepted the proposal made after the bug "when dragging an object in composes, it
usually snaps back with *an object cannot change its container*").

**Cause.** In composes an object hangs from a character of a paragraph, and that paragraph is its container in the
shared object layer (D177, D1023). The kernel refused every move to another container, since on a slide or a sheet that
would make it another object as far as locks and the stacking order go. So every drop near another paragraph was
refused; only drops within the paragraph it hung from worked. Moving a table by its name tab (D1229) to after another
paragraph went the same way.

**Decision.**

- **An app may let its objects change container** (`ObjectModel.objects_change_container`); composes does, creates and
  computes do not (a slide and a sheet stay as they are). `MoveObject` then takes the object out of the stack of its
  old paragraph and puts it **on top of the stack of the new one**. Its inverse remembers where it was in the old
  stack (`MoveObject.at`, written only when set), so undo puts it back exactly, also behind or in front of the others.
- **Where it hangs** is the rule of D1023, unchanged: the character nearest the object's top left corner, with the
  offset from there.
- **A move into a paragraph a colleague is writing in** is refused like any other edit there (`locked`): the place it
  is dropped on is one of the regions of the move. The object stays where it was.
- One step in the history, as before. The clients hear one `objects` event per paragraph: the old one loses it, the
  new one has it.
