---
id: D451
title: "Ctrl+F and Ctrl+H open the search panel from the document itself, in composes as in the other apps"
status: current
applies-to: all
date: 2026-11-14
round: "Search & replace in composes and creates (branch `search`)"
supersedes: []
superseded-by: []
---

# D451 · Ctrl+F and Ctrl+H open the search panel from the document itself, in composes as in the other apps

**Decision.** In composes the text is a contenteditable surface, not a text field. Ctrl+F and Ctrl+H therefore reach the window's shortcut handler from it and open the panel (D282), with the selected text as the first thing to find; only `INPUT` and `TEXTAREA` count as "a text field of its own" (`isTypingTarget`), and there the browser keeps its own find. In creates the same holds on the slide; while the words of an object are being edited (a textarea) the browser's find stays. Edit ▸ Search & Replace… (Ctrl+F) is in every app's Edit menu, in the GTK manifest and so in the generated Windows and macOS menus; Ctrl+H has no menu entry of its own (D281).

**Notes.** This amends the shortcut rule of D122 and D282, which said that the keys do not fire while a text has the focus: that was written for the formula bar. A text editor in which Ctrl+F opened the browser's find would never find what a replace is about to change, and could not search objects or notes at all. Alternative rejected: leaving Ctrl+F to the browser in composes and offering the panel only from the menu.
