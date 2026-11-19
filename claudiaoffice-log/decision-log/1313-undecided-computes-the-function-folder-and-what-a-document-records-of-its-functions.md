---
id: D1313
title: "The function folder, and what a document records of the functions it was calculated with (parked)"
status: undecided
applies-to: computes
date: 2026-11-19
round: "E1 core, closing out the open stories (branch e1-core)"
supersedes: []
superseded-by: []
---

# D1313 · The function folder, and what a document records of the functions it was calculated with (parked)

**Parked 2026-11-19 by the owner** ("we keep the functions folder parked for now to get started, I need to think about it"): nothing here is built or planned, and E1.9 goes on with the font half only (D1306). **Proposed 2026-11-19, not confirmed.** The owner asked for the function folder to be designed in E1.9 while macros and the `UserFunction` topic are parked (D1309). The design, its screens and its questions are in `notes/e1-function-folder.md`.

In short: user functions come from `--functions DIR` and `STATE_DIR/functions/` (through Server settings ▸ Functions), loaded through the existing `FunctionRegistry.register` plus a run of their examples, a bad file refused with its reason and never stopping the rest; a function's digest is the SHA-256 of its file; a workbook records, **inside its sealed content** as a logged non-undoable `StampFunctions` command, the `(name, version, digest)` of each user function it was calculated with, never in the plain manifest; on open the server runs the manifest check and tells people in a banner what is missing or changed, never blocking and never deleting a formula.

**Notes.** When confirmed this becomes `current` and completes the function half of E1.9 (D38, D1306 is the font half). It leaves open, on purpose, whether functions or macros may travel in documents.
