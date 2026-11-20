---
id: D1331
title: "A table at the end of the text gets an empty paragraph after it when the caret goes there"
status: current
applies-to: composes
date: 2026-11-20
round: "Bug fixes: tables and object sizes (branch fix-table-exit-object-sizes)"
supersedes: []
superseded-by: []
---

# D1331 · A table at the end of the text gets an empty paragraph after it when the caret goes there

**Decided 2026-11-20** (the owner accepted the proposal; the alternative was Word's rule that a table is always
followed by a paragraph, kept in the file).

When the table is the last thing in the text, there is nothing after it to write in. **An empty paragraph is made after
it when the caret is asked to go there:** the down arrow out of the table (D1330), a click in the space below the
table, and Ctrl+End. It is one entry in the history ("New paragraph") and undoes like any other. No paragraph is kept
there for its own sake: a text may end with a table, and an empty paragraph that was made this way and left empty
stays like any other empty paragraph. Going back into the table and out again uses that paragraph; no second one is
made.

**How.** The table hangs from a place in the paragraph before it (D1201), usually its end. An ordinary split at the end
of that paragraph (Enter) takes what hangs there along into the new paragraph, so the table would end up *after* the
new paragraph. The new wire method `add_paragraph_after` (`block`) splits with `keep`: what hangs exactly at the cut
stays where it is. `SplitBlock` writes `keep` only when it is set, so older logs read as before. Its inverse, the join,
gives back a split that keeps when the paragraph it took in had no objects of its own, so redo puts the table back where
it was too.

**Why not Word's rule.** A paragraph that must always be there has to be kept through every move, delete, import and
undo of a table, and is a stray empty paragraph in every export that does not need it. Import and export are not
changed by this decision.
