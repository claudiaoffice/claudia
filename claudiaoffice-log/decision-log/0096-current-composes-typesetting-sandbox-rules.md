---
id: D96
title: "Sandbox and output rules of the typesetting library"
status: current
applies-to: composes
date: 2026-11-03
round: "Fonts and typesetting services (sixteenth round)"
supersedes: []
superseded-by: []
---

# D96 · Sandbox and output rules of the typesetting library

**Sandbox and output rules of the typesetting library:** `-no-shell-escape`, `shell_escape=f`, `openin_any=p`, `openout_any=p`, a private job folder as `HOME`, a clean environment, no input, rlimits, a wall-clock limit, a process group killed whatever happens; documents may bring only data files, never class or package files; the SVG is accepted only if it passes an allowlist with no script, no outside reference, no DOCTYPE; results cached by job, engine version and catalogue digest, failures never.

**Notes.** Each rule has a test that fails when the rule is removed, checked by mutation for the sandbox flags.
