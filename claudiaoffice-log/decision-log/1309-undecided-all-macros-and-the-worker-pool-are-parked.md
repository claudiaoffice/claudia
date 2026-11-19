---
id: D1309
title: "Macros and the worker pool: parked until the owner has thought about what a macro is"
status: undecided
applies-to: all
date: 2026-11-19
round: "E1 core, closing out the open stories (branch e1-core)"
supersedes: []
superseded-by: []
---

# D1309 · Macros and the worker pool: parked until the owner has thought about what a macro is

**Parked 2026-11-19** by the owner. The first proposal (`notes/e1-macros-and-workers.md`, written the same day) is **not accepted**: it treated a macro as an automation script that runs on a snapshot and returns commands. The owner's reading is different, and this decision records it so that the next round starts from it:

* **A macro is a way to extend the Claudia apps themselves**, like a `UserFunction` in computes (D29: "functions or macros"), "not necessarily a tool for automation", although an automation tool is "also a great idea" and stays on the list as its own thing.
* **Whether macros belong in the document is open.** If they are installed on a server only, "there will be constant incompatibilities between servers when people send docs around". That question decides the design (where the code lives, what a document declares, what travels) and has to be answered first.
* **The `UserFunction` topic is parked with it**, except the *function folder* of E1.9, which is designed on its own (D1313).

**What stays true from the analysis** (checked again 2026-11-19, see the note): the pool on `main` runs only Office imports; the heavy-function work for computes (D291–D293 on branch `worker-pool`) is **not on `main`** and its decision numbers collide with `random-in-computes`'s; the macro API for composes and creates does not exist (D239).

**Notes.** Nothing here is built or planned. Until it is decided, D239 stays open and E4.4 (heavy functions in workers) stays `todo`.
