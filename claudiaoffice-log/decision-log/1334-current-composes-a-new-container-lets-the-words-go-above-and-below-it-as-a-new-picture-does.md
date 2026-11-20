---
id: D1334
title: "A new container lets the words go above and below it, as a new picture does"
status: current
applies-to: composes
date: 2026-11-20
round: "Bug fixes: tables and object sizes (branch fix-table-exit-object-sizes)"
supersedes: []
superseded-by: []
---

# D1334 · A new container lets the words go above and below it, as a new picture does

**Decided 2026-11-20.** A container put in with Insert ▸ Container (or pasted as a fenced block, D560) floated over the
words of the line it was put in and hid them, because it was sent without a wrap; a new picture, text box and shape get
"above and below" (D1061, `NEW_OBJECT_WRAP`). A new container now gets the same: the words stop above it and go on
below it. The person changes it with Wrap text… as for any object.
