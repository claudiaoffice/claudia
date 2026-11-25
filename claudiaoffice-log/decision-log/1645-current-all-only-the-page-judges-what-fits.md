---
id: D1645
title: "Only the page judges what fits; the desktop shells draw what it reports"
status: current
applies-to: all
date: 2026-11-25
round: "Menus architecture (branch `menus`, 2026-11-25)"
supersedes: []
superseded-by: []
---

# D1645 · Only the page judges what fits; the desktop shells draw what it reports

**Whether an entry fits is judged in the page alone, which runs in every client. The shell contract v1 gets two optional fields in `action_state`: `visible` per action, and `empty`, the "why" line per menu. A shell that does not know them greys instead.**

**Notes.** Only the page knows the role, the selection and the document; three judges would drift.
