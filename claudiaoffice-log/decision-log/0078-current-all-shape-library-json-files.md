---
id: D78
title: "Shapes are JSON files in a shape library"
status: current
applies-to: all
date: 2026-11-03
round: "Claudia creates, first draft (fourteenth round)"
supersedes: []
superseded-by: []
---

# D78 · Shapes are JSON files in a shape library

**Shapes are JSON files in a shape library.** Format version 1: `format`, `id`, `name`, `path`, optionally `aspect` and `text_area`. The `path` is a string of absolute `M`, `L`, `C`, `A`, `Z` commands in a 100×100 box with a strict grammar. A library is a folder; a later folder replaces a shape of the same id; a bad file is skipped and listed at start-up.

**Notes.** The owner asked for JSON everywhere: the file is JSON; only the outline is a path string, because a path of hundreds of numbers is unreadable as nested arrays.
