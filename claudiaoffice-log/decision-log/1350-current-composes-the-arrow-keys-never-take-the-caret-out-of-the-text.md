---
id: D1350
title: "The arrow keys never take the caret out of the text: Up on the first line goes to its start, Down on the last to its end"
status: current
applies-to: composes
date: 2026-11-20
round: "Bug fixes: stale tests, the caret, dragging objects (branch fix-stale-tests-caret-drag)"
supersedes: []
superseded-by: []
---

# D1350 · The arrow keys never take the caret out of the text

**Decided 2026-11-20** (the owner accepted the proposal made after the bug "moving past the first word of a composes
document": the caret seemed to go to a line above the first one, and what was typed then still went in front of the
first word).

**Up on the first line of the text puts the caret at the start of the text; Down on the last line puts it at the end
of the text.** With Shift, the selection is extended to the start or the end. This is what most editors do. The keys are
taken by the editor there, not left to the browser: Firefox moves its caret out of the first paragraph into the editing
area around it, where it is drawn above the text; and right after typing, before the words were sent, Chromium put the
caret at the end of the line.

Only the main text of composes; the words of a text box or a shape are written in another editor, which is changed only
if it shows the same. The other arrow keys, Home, End and the keys of a table (D1330) are not touched.
