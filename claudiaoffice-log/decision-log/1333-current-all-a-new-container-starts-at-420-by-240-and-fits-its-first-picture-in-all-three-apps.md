---
id: D1333
title: "A new container starts at 420 × 240 and fits its first picture, in all three apps"
status: current
applies-to: all
date: 2026-11-20
round: "Bug fixes: tables and object sizes (branch fix-table-exit-object-sizes)"
supersedes: []
superseded-by: []
---

# D1333 · A new container starts at 420 × 240 and fits its first picture, in all three apps

**Decided 2026-11-20.** D1229 says a new container is no bigger than 420 × 240 or its own picture "in all three apps".
Composes and computes asked for 420 × 240 with `fit`; creates asked with `fit` too, but for the frame of a new picture
(427 × 240, at 16:9), so its containers started a little larger. (The first reading, that computes did not fit, was
wrong: its session adds `fit` itself.)

Now **all three apps ask for 420 × 240 with `fit`**, in their own units, and the server fits the first picture to it
and to the least of D1332. Creates places a new container where it places any new object (a little further from the
first for each new one), with that size (`insertFrame('container', …)`).
