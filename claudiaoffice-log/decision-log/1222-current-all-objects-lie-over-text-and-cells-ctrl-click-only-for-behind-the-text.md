---
id: D1222
title: "Objects lie over the text and the cells, so a click selects them; only an object behind the text needs Ctrl"
status: current
applies-to: all
date: 2026-11-18
round: "Object interaction in the three apps (branch object-interaction)"
supersedes: []
superseded-by: []
---

# D1222 · Objects lie over the text and the cells, so a click selects them; only an object behind the text needs Ctrl

**Text and cells are always at the bottom of the stack; an object lies over them, so a click on it selects it, and to reach what is under it a person moves the object.** The one exception is composes' wrap *behind the text* (D1061), where the words are above the object: there a plain click is for the words and **Ctrl+click takes the object** (D1063, which stays for exactly that case; Tab and Edit ▸ Select Next Object reach it without a pointer).

**Notes.** The owner, 2026-11-18, answering which of D1063's rule and "a click selects" wins: in nearly all cases the object is shown on top, so it simply selects; the Ctrl rule is for the single case where the wrap puts text above an object.
