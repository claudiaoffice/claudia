---
id: D1302
title: "E1.10 closes without person-defined colour roles and without upcasting of dropped properties"
status: current
applies-to: all
date: 2026-11-19
round: "E1 core, closing out the open stories (branch e1-core)"
supersedes: []
superseded-by: []
---

# D1302 · E1.10 closes without person-defined colour roles and without upcasting of dropped properties

**Decided 2026-11-19** by the owner (taking the proposals).

* **A command that lets a person define a colour role of her own is its own story**, no longer part of E1.10. Today `ReplacePalette` brings a different set of the nine roles (D200–D202) and nothing adds a tenth.
* **Upcasting of dropped CSS properties is struck from E1.10.** It was already not wanted before the first release (D308: no migration while Claudia is pre-release); this removes it from the story's list of what is "not done".

**Notes.** With D1300 and D1301 and the screens of D783, E1.10 has nothing open on the style model. The story is closed in the patch that carries the tests for those two decisions.
