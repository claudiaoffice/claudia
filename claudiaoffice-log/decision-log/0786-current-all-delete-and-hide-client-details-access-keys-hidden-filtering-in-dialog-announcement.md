---
id: D786
title: "Delete and hide, client details: access keys, hidden styles leave the menus, the announcement stays in the dialog"
status: current
applies-to: all
date: 2026-11-18
updated: 2026-11-18
round: "Deleting and hiding styles (E1.10)"
supersedes: []
superseded-by: []
---

# D786 · Delete and hide, client details

Choices made while building D783 that the mock left open:

* **Access keys.** The row buttons act on the row the focus is on with Alt + the first letter of the translated label (English: E edit, R rename, D delete, H hide/show). Derived from the label, so every language gets its own letters; the dialog says so in a hint line. No new shell-contract entries: *All Styles…* (Ctrl+Alt+Shift+A) already opens the dialog (D301), so the GTK and neutralino shells needed only the description text of the entry.
* **Hidden styles leave menus and pickers** (the Format menu list, *Apply Style…*, galleries), except the style the selection has now. They stay in All styles behind *Show hidden styles*.
* **The announcement is in the dialog**, not a toast: it carries *Name it…* and *Undo*, and a toast would vanish before a person can name the stand-in.
* **Refusals are shown inside the Delete dialog** (somebody used the style meanwhile, a target that cannot hold the look), next to the buttons, so the person can pick another way.
* **Assign re-bases the children of the deleted style on the chosen style**, not on the deleted style's parent (D785).
