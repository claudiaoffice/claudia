---
id: D1023
title: "A floating object keeps a free offset from the character it hangs from"
status: current
applies-to: composes
date: 2026-11-15
round: "Rotation in the three apps (branch rotation-ui)"
supersedes: []
superseded-by: []
---

# D1023 · A floating object keeps a free offset from the character it hangs from

**`BlockAnchor(block, offset, dx, dy)`: the object hangs from a character as before (D179) and sits `dx`, `dy` CSS pixels from where that character is.** Both are whole numbers within ±10 000 (`MAX_ANCHOR_OFFSET`). An anchor without them reads as 0, 0, so documents written before this decision load unchanged and the wire form needs no new version. The offset follows the anchor through typing, splitting, joining and undo (`followed`, `carried_to`); only moving the object changes it. `move_object` takes optional `dx` and `dy` and keeps the object's own when they are left out.

**Why.** Without an offset an object could only sit *on* its anchor character; to put a stamp in the margin or a picture beside the paragraph the person would have had to hang it from a character at that place. With it, dragging an object moves the offset, and the anchor character is only the thing that keeps the object with its text (owner, 2026-11-15: "yes! I want them! in the model, and the UI").

**Notes.** Amends D179 (the anchor still follows the text) and D907: print puts the object's top left at the anchor character's place plus (`dx`, `dy`), then keeps it inside the margins. A turn never changes the anchor or the offset. Whether a dashed tether is drawn from the object to its anchor character while it is held is the client's business (D1024).
