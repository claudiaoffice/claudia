---
id: D1202
title: "A table sits in the flow by default and may float; placement belongs to the table, the wrap to the object layer"
status: current
applies-to: composes
date: 2026-11-18
round: "Tables in composes (branch tables-in-composes)"
supersedes: []
superseded-by: []
---

# D1202 · A table sits in the flow by default and may float; placement belongs to the table, the wrap to the object layer

**A table has a placement, `flow` (the default) or `float`.** In the flow it takes its own place after the paragraph it hangs from, as wide as the text or a width the person set, and splits between rows across pages with its header rows repeated. Floating is a narrow table beside text; it takes the wrap modes the `floating-objects` branch is deciding (over, around, above and below, behind) once the object layer has them.

The placement is a field of the table's definition, not of `BlockAnchor`: the anchor is the object layer's and another branch (`floating-objects`) is changing it. The anchor still follows the text (D179), so a table follows the paragraph it hangs from when that is split or joined; `dx` and `dy` apply to a floating table only.

**Notes.** The owner's first picture was "a table is an object around which text wraps"; the object is right, the default is the flow, because a table's height comes from its words and it must be allowed to run over pages (confirmed 2026-11-18, "placement default: go with your recommendation"). Only the floating placement waits for `floating-objects`; the model, server, layout, editor and files do not.
