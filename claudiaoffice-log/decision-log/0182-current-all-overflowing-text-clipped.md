---
id: D182
title: "Text that does not fit an object is clipped at its border"
status: current
applies-to: all
date: 2026-11-08
round: "PNG, and an object's words as a paragraph (thirty-second round)"
supersedes: []
superseded-by: []
---

# D182 · Text that does not fit an object is clipped at its border

**Text that does not fit an object is clipped at its border.** No scrolling, no shrink-to-fit, no growing the box, and nothing pushed aside: what is past the border is simply not drawn. A paragraph inside an object is never split or joined either — it has a box of a fixed size, where a paragraph of a document has a page that flows. This is the per-host difference the shared-paragraph work had to settle, and settling it this way is what keeps the entity shared: everything *else* about a paragraph is the same in all three apps.

**Notes.** The owner's specification. Nothing in the model enforces it — it is the view's part — but it is recorded here because this is where the question was asked, and because the alternative (a box that grows, or text that reflows around objects) would have made an object's paragraph a different entity from a document's rather than the same one. Text wrap in composes, where words flow *beside* a floating object, remains a separate and unbuilt feature (D179).
