---
id: D748
title: "Every entry the shell keeps on the start page's menu has an action on that page"
status: current
applies-to: all
date: 2026-11-24
round: "The Windows installer, first real install (CODE-84; branch `win-installer-fix`)"
supersedes: []
superseded-by: []
---

# D748 · Every entry the shell keeps on the start page's menu has an action on that page

**The shell's short menu of the start page (sheet 11, the manifest's `start` actions: New, Open…, Open a File…, Dark Mode,
App Language, Quit, About) and the page's own list of what it does for them are one list.** The page's list is
`startPageAction` (`web/app/lib/open.ts`); `help.about` is on it and opens the About dialog of the window's app.

**Why.** The first real Windows install: Help ▸ About worked in an open document and did nothing on the start page. The
shell sent the action; the start page's handler did not know it. Windows and macOS have no About dialog of their own (only
the Linux client does, and it never sends the action to the page), so the page's dialog is the About of those two.

**Notes.** The two lists are still two lists: a menu entry added to `_START_ACTIONS` in `manifest.py` needs a case in
`startPageAction`. A test that reads the manifest and asks the page for each `start` action would hold them together; not
written here (the manifest is Python, the page TypeScript).
