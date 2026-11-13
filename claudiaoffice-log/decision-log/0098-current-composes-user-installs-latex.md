---
id: D98
title: "Installing LaTeX is the user's job; Claudia is told where it is"
status: current
applies-to: composes
date: 2026-11-03
round: "Fonts and typesetting services (sixteenth round)"
supersedes: []
superseded-by: []
---

# D98 · Installing LaTeX is the user's job; Claudia is told where it is

**Installing LaTeX is the user's job; Claudia is told where it is.** `Typesetter(xelatex=…, pdftocairo=…)` take a full path, a folder or a PATH name; symlinks are not followed; the working folder is never searched. Resolution is lazy: a server without LaTeX starts and the first job says what is missing. `Typesetter.diagnose()` checks everything and gives a hint. **Nothing is bundled.**

**Notes.** Replaces the bundling plan for Windows and macOS. `pdftocairo` belongs to poppler, a separate install there. The server option and settings screen are not wired.
