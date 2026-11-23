---
id: D1539
title: "Change theme and Change template match by id and name, replace what matches, add what is new and delete nothing"
status: current
applies-to: creates
date: 2026-11-23
round: "E10.4 Templates, layouts and placeholders (branch e10-4-templates-and-layouts)"
supersedes: []
superseded-by: []
---

# D1539 · What Change theme and Change template do with what the presentation has

The owner agreed the rules on 2026-11-23. Both are one step with one undo (D1531: the plan carries final values).

**Change theme** (`change_theme`, `claudia_core.theme_commands`): the styles and the colours of a template, nothing else.

* A built-in style is matched by its id, any other style by its name ignoring case. A matched style takes the CSS of the
  theme; its parent, headings, numbering and name stay. A style the presentation lacks is created.
* The theme's colours replace the colours of the presentation with the same role id, add the ones it lacks, and leave
  the ones only the presentation has. (`ReplacePalette` refuses a palette that lacks a role a style uses, so the new
  palette is always the presentation's roles with the theme's on top.)
* Layouts and slides are not touched. Nothing happens, and no step is made, when it looks like that already.

**Change template** (`change_template`): the theme, and then the layouts.

* A layout is matched by name ignoring case. A matched layout keeps its id, its name and its slides and gets what is on
  the template's layout; a box of a slide that was bound to one of its placeholders follows the placeholder with the
  same purpose, and where there is none it stays a free box where it stands. A layout the presentation lacks is added.
* Nothing the presentation has of its own is deleted: not a layout, not a style, not a colour.
* The presentation keeps a note of the template (`SetTemplate`), the same note a new presentation has. Nothing follows
  it afterwards.

Considered and rejected: matching styles by name only (a built-in style may be renamed in the template); deleting what
the template lacks (a slide would lose its look without anybody asking).
