---
id: D28
title: "About dialog"
status: current
applies-to: all
date: 2026-11-01
round: "Common to all three apps"
supersedes: []
superseded-by: []
---

# D28 · About dialog

One good-looking **About dialog** shared by all apps, showing each app's own logo icon.

**Notes.** Built by hand on `Adw.Dialog` in the Linux shell, not `Adw.AboutDialog` — its own Website/Troubleshooting/Legal row is oversized next to the web app's buttons (owner's report, 2026-11-06); a shared web component elsewhere. Both sides read the same three links (Website, Report an Issue, Legal) in the same order (`manifest.py`'s `about_links()`, `AboutDialog.vue`'s `LINKS`). Patch exists, not yet committed (PROC-03) — see `notes/e5-1-e5-10-menus-and-accessibility.md`.

**Checked against the code, 2026-11-17 (`main` at `6814bac`).** Committed since: `web/app/components/AboutDialog.vue` and `manifest.py`'s `about_links()` are in `main`.
