---
id: D30
title: "getTooltip and getHelp"
status: current
applies-to: all
date: 2026-11-01
round: "Common to all three apps"
supersedes: []
superseded-by: []
---

# D30 · getTooltip and getHelp

Every UserFunction has **getTooltip and getHelp** methods returning renderable help text in **LaTeX**. The user doc and help system is based on this.

**Notes.** Built as a mandatory description plus at least one `Example` in `functions/base.py`. The LaTeX help text and the help system are not built. Widened by D88.

**Checked against the code, 2026-11-17 (`main` at `6814bac`).** The help system exists since (E13.3: `claudia_server.help`, `help_search`, `function_help`); functions carry a description and examples, served as tooltip and help. A LaTeX help text per function is still not built.
