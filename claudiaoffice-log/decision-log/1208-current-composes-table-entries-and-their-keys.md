---
id: D1208
title: "The table entries of the Insert and Edit menus and their keys (provisional, to be checked for consistency)"
status: current
applies-to: composes
date: 2026-11-18
round: "Tables in composes (branch tables-in-composes)"
supersedes: []
superseded-by: []
---

# D1208 · The table entries of the Insert and Edit menus and their keys (provisional, to be checked for consistency)

**Insert ▸ Table… Ctrl+Shift+F. Edit ▸ Table Options… Ctrl+Shift+L ("look"). Edit ▸ Merge Cells Ctrl+Shift+G. Edit ▸ Split Cell Ctrl+Shift+H. Edit ▸ Sort ▸ Ascending Ctrl+Shift+X, Descending Ctrl+Shift+Y.** Edit ▸ Row and Column are computes' own entries with computes' own keys (Shift+Alt+arrows, Ctrl+Alt+- and Ctrl+Alt+_); they appear in composes only while the caret is in a table. All of them are in the shared manifest, so the Linux, macOS and Windows shells get them from there.

**Why these chords.** Every Ctrl+Alt letter and every Ctrl+Shift+Alt letter in the manifest is taken or refused (D627 met the same wall; Ctrl+Alt+T is the Ubuntu terminal, E, M, Q and the digits are AltGr); Ctrl+Shift+Alt with an arrow moves a window to another workspace on GNOME. What is left are the Ctrl+Shift letters that no browser keeps and the manifest does not use. They are **provisional**: the owner said "assign some key, I don't care; keep as much consistency across the apps as possible" and will ask the agent that looks after keys. The same action has the same key in every app (`test_one_action_has_one_key_in_every_app`); computes and creates do not show these entries.

**Notes.** The first mock had Ctrl+Alt+T and Ctrl+Shift+Alt+E: the first is refused by the manifest test, the second is planned for Redact History (`notes/redaction-ui.md`).
