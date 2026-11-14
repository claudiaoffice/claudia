---
id: D361
title: "Every menu entry is in every client's menu"
status: current
applies-to: all
date: 2026-11-13
round: "QA follow-up: UX consistency across clients (UX-35, UX-36)"
supersedes: []
superseded-by: []
---

# D361 · Every menu entry is in every client's menu

**What the web menus have, the desktop menus have, and the other way round.** A test reads the web sources and fails
for a web menu entry that is not in the manifest, as the older one fails for a manifest entry the web lacks. The
exceptions are named with their reason (the parents of flyouts, dynamic lists such as style names and the shape
library). This round added to the desktop menus: File ▸ Print… (composes, creates), Format ▸ List ▸ in every app (as on
the web, disabled where there are no paragraphs), Edit ▸ Image… and Chart…, Format ▸ Clear Cell Style, Tools ▸ Names…
and SQL Query… (computes), Edit ▸ Image… and View ▸ Show Grid (creates). The two characters that had keys and no menu
entry got one in both: composes' Edit ▸ Insert ▸ Soft Hyphen / Non-breaking Hyphen.

**Labels are in the title case of the GNOME HIG on the web too** ("Show Grid", "SQL Query…", "Bulleted List"), so an
entry has one label, one translation and one key everywhere. View ▸ Show Grid follows the shared View entries, as
composes' Page does.

**Notes.** Owner's request of 2026-11-13: "add all features to menus (e.g. Printing) both in web app as well as every
desktop client". QA found (UX-36) that the desktop shells hide the web menu bar, so an entry only on the web could not
be found on the desktop. computes has no printing yet, so it has no File ▸ Print….
