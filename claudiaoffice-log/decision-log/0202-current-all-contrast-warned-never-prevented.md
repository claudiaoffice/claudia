---
id: D202
title: "Contrast is checked, reported in plain words, and never prevented — and the ratio is never shown to a reader"
status: current
applies-to: all
date: 2026-11-08
round: "Colour roles: the document's palette (thirty-third round)"
supersedes: []
superseded-by: []
---

# D202 · Contrast is checked, reported in plain words, and never prevented — and the ratio is never shown to a reader

**Contrast is checked, reported in plain words, and never prevented — and the ratio is never shown to a reader.** `PAIRINGS` says which roles are read against which and the floor each has to clear: 4.5:1 where it is words, 3:1 where it is a border or a rule (WCAG 2.2 AA, the same floors the suite's own tokens are built on). `Palette.readings()` works out the ratios; a `Reading` travels as `{foreground, background, ratio, floor, ok, words}` and carries **no verdict text**, so each client says what a failure means in its own words. The warning a person sees is "White on this yellow will be hard to read", not "1.42:1". `attention` and `highlight` are deliberately not paired: they are ornament in the built-in styles, and WCAG's 3:1 is for what a reader must make out to use or understand a page.

**Notes.** The owner's decision on both halves: warn, never prevent ("users might mess up contrast etc. but we'll only warn them about it"), and then, seeing the mockups, that a ratio "will not be understood by ordinary users". The pairings were cut back for an honest reason, not a convenient one: paired at the UI floor, a brand-new document reported its own Highlight as too faint (apricot on paper is 1.99:1), which is exactly how a warning teaches people to ignore warnings. The day either role carries words or a boundary, it gets a pairing and the check comes with it.
