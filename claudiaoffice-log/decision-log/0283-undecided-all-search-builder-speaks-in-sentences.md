---
id: D283
title: "The pattern builder speaks in sentences: parts to find, conditions on the cell, a restatement, and why something was left out"
status: undecided
applies-to: all
date: 2026-11-13
round: "Search & replace in all three apps (branch `regex-builder`)"
supersedes: []
superseded-by: []
---

# D283 · The pattern builder speaks in sentences: parts to find, conditions on the cell, a restatement, and why something was left out

**Find** is a list of **parts**, in order. A part says **what** (the text "…", any one of these characters, none of these characters, a letter, a digit, a space, a number, the start or end) and **how many** (once, optional, one or more, any number, exactly n, n to m), and may be **kept** under a name for use in the replacement. **Only in cells that…** is a list of **conditions** on the whole cell (contain, do not contain, start with, end with, are exactly), joined by "all of" or "any of". The panel **restates the pattern as a sentence** ("Finds any one of € $ £ in cells that do not contain “EUR”."), shows the matches live, and lists what looks similar but was **left out, with the reason**. **The quick find field is always plain text**, never a pattern: what is typed is what is found, so “(2027)” or “a.b” need no care. Match case, whole cell (whole word in text apps) and the place to search are plain toggles. An app can add parts of its own (computes: a cell reference, a function name; composes: a word).

**Writing the pattern yourself** is in the panel's ⋯ menu. It shows three fields — Find, Only in cells matching, Replace — starting from the pattern the builder made, checks it **while typing** with one sentence and a character position per mistake, and offers a sample text to try it on. Once the text is edited the builder can no longer show it; "Back to the builder" returns to its last state after a confirmation.

**Notes.** Claude's proposal, from the owner's example ("string X should not occur, but at least one of those characters"): that is one condition and one part. The two-level split (span to replace, conditions on the cell) exists because a replacement needs a span and "does not contain" has none; with no part given the whole cell is the match. Shown in `computes-search-builder.svg` and `search-pattern-as-text.svg`. Every builder phrase is a whole translatable string with placeholders, never glued from pieces (E5.7).
