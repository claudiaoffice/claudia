---
id: D223
title: "Help system (D76), none decided"
status: undecided
applies-to: all
date: 2026-11-10
round: "Open design questions"
supersedes: []
superseded-by: []
---

# D223 · Help system (D76), none decided

**Help system (D76), none decided:** the topic file format, the search service, whether an extension without help is refused in composes and creates too, where the help view lives, and whether tooltips could default from docstrings. **And now also:** Help's "How do I…?" and "Documentation" ship as visible, inert stubs until this exists, and today's Help ▸ Keyboard dialog content moves into Config ▸ Shortcuts instead of staying in Help (D125, D126).

*Carried over on 2026-11-10 from the decision log's "Open design questions" section, which had no numbers. Nothing here is decided yet.*

**Checked against the code, 2026-11-17 (`main` at `6814bac`).** Settled by the code since: the topic file format is D99's Markdown with front matter (`claudia_server.help`); search is `help_search` over title, tags and what a topic explains; the help view is a tab of the docked panel (`HelpPanel.vue`); Help ▸ How Do I…? and Documentation open it and are no longer inert stubs (`document-menus.ts`). Still open: whether an extension without help is refused in composes and creates, and tooltips from docstrings.
