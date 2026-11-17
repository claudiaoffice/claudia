---
id: D346
title: "Defaults for the audience screen and the presenter view, proposed and not yet confirmed"
status: current
applies-to: creates
date: 2026-11-13
round: "Presenter mode in creates (E10.2, branch `presenter`)"
supersedes: []
superseded-by: []
---

# D346 · Defaults for the audience screen and the presenter view, proposed and not yet confirmed

**Undecided; proposed, and not objected to, but not confirmed either.** Audience screen: the slide only, on Ink, no chrome, pointer and controls hidden after two seconds without movement; transitions none, or one 150 ms fade that `prefers-reduced-motion` switches off; no builds, no hidden slides, forward is the next slide in order. Presenter view: Ink surface, current slide, next slide, Markdown notes at reading size, the clock, the time against the plan (D343); `G` overview, `B` blank, `P` swap; the docked panel is hidden and the AI is not used while presenting; the audience view announces the slide title to screen readers (BITV). The entries are in the View menu with a Present button in the bar.

**Notes.** Questions 6–10 of the first draft of `notes/e10-2-presenter-mode.md`. Screens A–G of `notes/mockups/presenter-mode.svg` are not yet agreed; the rule is to agree screens before code.

**Checked against the code, 2026-11-17 (`main` at `6814bac`).** Built as proposed: the audience view hides the pointer after two seconds without movement and fades in 150 ms, switched off by `prefers-reduced-motion` (`PresentShow.vue`); the presenter view, overview, blank and swap are the show's commands (`lib/show.ts`). Screens A–G were agreed on 2026-11-13 (E10.2). The owner made the code the record of what is decided (log audit of 2026-11-17), so the status is current; replace it with a new decision to change it.
