---
id: D298
title: "Alternatives go into Excel and OpenDocument files as the first value plus a note"
status: current
applies-to: computes
date: 2026-11-13
round: "Random numbers, alternatives and following a computation (branch random-in-computes)"
supersedes: []
superseded-by: []
---

# D298 · Alternatives go into Excel and OpenDocument files as the first value plus a note

**Neither format has a counterpart for an input with several values, so an alternatives cell is written as its first alternative with a cell note** (xlsx comment, ods annotation) reading `claudia alternatives: {…}`. Reading the file again restores the alternatives only if the cell still holds the first one — someone who changed the value in Excel meant that value. The note is claudia's: other comments are kept as comments and reported as before.

**Notes.** Rejected: writing a scenario manager (Excel's differs in meaning), hiding the data in a custom XML part (invisible and lost by other programs' saves).
