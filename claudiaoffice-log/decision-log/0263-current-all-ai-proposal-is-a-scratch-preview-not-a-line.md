---
id: D263
title: "An AI proposal is a scratch preview, not a line"
status: current
applies-to: all
date: 2026-11-11
round: "The AI agent: rights, modes and proposals (E7)"
supersedes: []
superseded-by: []
---

# D263 · An AI proposal is a scratch preview, not a line

**In suggest mode an AI proposal for computes or creates is a stored batch of commands plus the revision it was computed at, kept with the chat record; nothing reaches the log until it is accepted.** The person previews it on a scratch copy of the document that only she sees, from the history panel; accepting replays the batch on the current head as the accepter, tagged `via ai`. It is not a line (D48): no fork, no checkpoint, no merge. The cells or objects it touches are *marked*, not locked; a proposal becomes *outdated* when anything in its footprint changes (in the first version, any row, column or sheet change in the sheet it touches); accepting an outdated one shows a conflict prompt, never an automatic rebase, and the AI can redo it against the current state. In suggest mode the AI's read-act-correct loop runs against the scratch copy; in act mode it runs against the live document.

**Notes.** Reuses the scratch model of D149 (`peek_line`, `materialize`) and the local-only preview of history entries, not the stored fork and switch of D48/D51. A line is document-wide and exclusive (a switch rebuilds everyone's view, clears locks and presence and swaps undo stacks), and each rejected proposal would leave a hidden line behind (D235). A lock on the footprint was rejected: a proposal may wait an hour and could block a colleague's column. This is a what-if primitive, not free branching: D236 stays undecided. **Not verified:** that a throwaway document over `materialize` can execute commands (`peek_line` returns a model, not something that runs them), what building one costs on a large workbook (build it on demand), and how proposals look for objects in creates. In creates the preview shows the proposed objects as ghosts on the slide, which E10.6 lists as not done. Composes keeps its persisted, text-anchored suggestions.
