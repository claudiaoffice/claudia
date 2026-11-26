---
id: D1644
title: "The web's menus are assembled from the definition and the actions each workspace carries out"
status: current
applies-to: all
date: 2026-11-25
round: "Menus architecture (branch `menus`, 2026-11-25)"
supersedes: []
superseded-by: []
---

# D1644 · The web's menus are assembled from the definition and the actions each workspace carries out

**The web stops building its menus by hand. Each workspace keeps only what each action does (and a label or a tick where those change); the menus and context menus are assembled from the definition. A test checks that every action of an app's definition is carried out and that nothing is carried out that the definition does not name.**

**Notes.** Chosen over keeping the hand-built menus with a test that compares them. Every place that greys an entry today is listed before it is replaced; one that matches no condition of the workbook goes to the owner.
