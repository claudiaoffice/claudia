---
id: D1223
title: "Selecting an object holds it in all three apps, as it does in creates"
status: current
applies-to: all
date: 2026-11-18
round: "Object interaction in the three apps (branch object-interaction)"
supersedes: []
superseded-by: []
---

# D1223 · Selecting an object holds it in all three apps, as it does in creates

**In computes and composes too, selecting an object holds it** (a lock on an `ObjectSet`): the holder sees the handles, others see her coloured outline and name tag, and a move, a resize or a turn is previewed locally and sent as one command on release. This extends D82, which was written for creates; computes kept its selection local and composes' was shared without a lock.

**Notes.** The owner, 2026-11-18 ("all three hold"). D82 is unchanged and still says how it works in creates. A colleague now sees in computes and composes what she already sees in creates.
