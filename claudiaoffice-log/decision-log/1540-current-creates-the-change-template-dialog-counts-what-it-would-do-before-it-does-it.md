---
id: D1540
title: "The Change template dialog counts what the change would do, before it is done"
status: current
applies-to: creates
date: 2026-11-24
round: "E10.4 Templates, layouts and placeholders (branch e10-4-templates-and-layouts)"
supersedes: []
superseded-by: []
---

# D1540 · A read method that counts the change

Mock M of the Change template dialog shows what the change would do before the person presses it. The server therefore
has a read method `template_change_preview(template)` that answers ten numbers, counted from the same matching the
change uses (D1539), so that what is said and what happens cannot drift apart:

* styles and colours: replaced (a matched one that looks otherwise), added, and, for styles, the presentation's own that
  the template has no match for and that stay; for colours, the number replaced and the number added;
* layouts: matched by name, added, and the presentation's own that stay;
* slides: those that follow a matched layout and so take what is on it, and those that do not.

The method changes nothing. Change theme does the first five only. The mock also has "Show the slides…", a list of the
slides counted as reframed. It is **not built**: the preview counts and names no slide, so the list would need the
method to answer their ids as well. The owner decides whether it is worth that (see the implementation note).

Considered and rejected: a dry run that applies the change to a copy and compares (slow for a large deck, and it counts
effects, not decisions); showing no summary (the person would learn what the change did only from Undo).
