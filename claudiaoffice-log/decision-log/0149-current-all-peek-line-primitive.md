---
id: D149
title: "A new kernel primitive, `Document.peek_line(line)`: a read-only look at any line's state at its head, on a scratch model, without switching to it"
status: current
applies-to: all
date: 2026-11-07
round: "Restore with consent, and the line picker (twenty-sixth round)"
supersedes: []
superseded-by: []
---

# D149 · A new kernel primitive, `Document.peek_line(line)`: a read-only look at any line's state at its head, on a scratch model, without switching to it

**A new kernel primitive, `Document.peek_line(line)`: a read-only look at any line's state at its head, on a scratch model, without switching to it.** Owner, asked directly ("is a `peek_line()` in the core the way to do this?"): "Yes, let's have a `peek_line()` in the core."

**Notes.** A thin wrapper around the existing `materialize`; touches nothing else (no mutation of the active line, undo steps or checkpoints). Lets the Lines picker (D52) show a hidden line's content before anyone proposes switching to it, instead of requiring a switch first and a switch back if it turns out to be the wrong one.
