---
id: D1455
title: "The step code of the names spec chooses Name & describe… from whichever menu has it, until the menu rework moves it"
status: current
applies-to: all
date: 2026-11-22
round: "E2E guard follow-up (E1.13 step code, branch e2e-guard)"
supersedes: []
superseded-by: []
---

# D1455 · Name & describe… is chosen from whichever menu has it

**Made while writing the step code of `specs/objects/names.feature`, 2026-11-22; for the owner to veto.**

The spec says *Edit ▸ Name & describe…* (and *Edit ▸ Reference in Chat*). Today the entry is under **Format** in all
three apps; the move to Edit belongs to the menu rework, which is delayed. A step that clicks *Edit* would fail for a
reason the scenario is not about, and a step that clicks *Format* would fail the day the rework lands.

So `choose(person, entry)` in `tests/e2e/specs/test_names.py` opens the top menus in turn and clicks the entry in the
first one that has it, matched from the start of its label (`Person.menu_item`). Which menu an entry is in is checked
by `claudia-menus.xlsx` and its tests, not by this spec. When the menu rework is done, the steps can name *Edit* again;
nothing else changes.
