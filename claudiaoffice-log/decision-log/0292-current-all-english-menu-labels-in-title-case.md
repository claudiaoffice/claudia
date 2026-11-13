---
id: D292
title: "English menu labels are Title Case in the web app as in the GNOME shell"
status: current
applies-to: all
date: 2026-11-13
round: "Complete internationalization (branch i18n)"
supersedes: []
superseded-by: []
---

# D292 · English menu labels are Title Case in the web app as in the GNOME shell

**The menu and action labels of the web app use Title Case ("Paste As", "Dark Mode", "Edit This Style…"), the form the GTK manifest already used (GNOME HIG).** D160 noticed the split (about 28 labels were sentence case in the web app and Title Case in the shell) and left it alone. The owner chose to unify it in 2026-11-13, to Title Case. Menu entries, dialog buttons that repeat a menu entry and the context menu follow it; tooltips, hints, `aria-label`s and sentences stay sentence case ("Bulleted list (Ctrl+Shift+8)"), and a short noun used as a heading ("History", "Colours") is one word anyway.

**Notes.** Both forms are one msgid now, so the German catalog has one translation for each, and the end-to-end scripts that click a menu entry by its text (`web/e2e/*.cjs`) were changed with it. A new menu label is written in Title Case; the pseudo-locale (`po/xx.po`) shows a label that was not wrapped.
