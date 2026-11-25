---
id: D1646
title: "Rules are written in the workbook's words and checked against a registry of conditions"
status: current
applies-to: all
date: 2026-11-25
round: "Menus architecture (branch `menus`, 2026-11-25)"
supersedes: []
superseded-by: []
---

# D1646 · Rules are written in the workbook's words and checked against a registry of conditions

**An entry's rule in the definition is the workbook's "Fits when" text, word for word. The page parses it against a registry with one entry per condition; a phrase the registry does not know fails the build, it never hides an entry.**

**Notes.** Word for word makes the test of D1605 a plain comparison. A new condition is one entry in the registry (D1601).
