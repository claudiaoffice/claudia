---
id: D2005
title: "An imported export brings the history and chat of the original as one read-only note of its import step"
status: current
applies-to: all
date: 2026-11-25
round: "Bug eater, batch 4 (branch batch-4): PROC-37"
supersedes: []
superseded-by: []
---

# D2005 · An imported export brings the history and chat of the original as one read-only note of its import step

**Decided 2026-11-25** (the owner chose option (a) of PROC-37: a read-only "History of the original", text only, the
names as text).

D1272 said that the history and chat of an owner's export come back in with their authors as text ("former people"). The
history of an export is the commands of another document, with revisions that mean nothing in the new one; what a person
wants of it is who did what and when, not steps to undo. Now:

- **Where.** The note is part of the new document's single `core.Import` step (`Import.original`), not a step of its
  own. The import is nobody's undo step (D438), so the note is not either: no undo removes it, and the history keeps one
  step for the import as before. Its data is written only when there is a note, so an import without one is stored as
  before.
- **What.** One line per step of the original, on every branch, as `{when, who, what}`: `what` is the sentence the
  original's history panel said of the step (its `summary`, with `undo ·` or `redo ·` in front as the panel shows it),
  or the command's kind for a step this version cannot read. Oldest first. The names are text: nobody named is given an
  account, a key, a place in presence or in the people list (D1272), and `ai` stays the AI.
- **The chat**, by the same reasoning: its messages are already text, who said what and when, and a message's place in
  the original's history means nothing in the new one. A message **for everybody** becomes a line of the same note
  (`said: true`, its words; a redacted one keeps that it was said, without words). A **private** message stays out: it was
  for two people, and the note is read by every owner and editor of the new document.
- **Who reads it.** It is history: `log` gives it as `original` of the import step, to whoever may read the history
  (D1261). A viewer does not see it.
- **The web.** The import's step in History & Chat has a folded "History of the original" with a line per entry (the day
  and time in the reader's own calendar, the name, what was done or said) and a sentence that the names are people of
  the original document without access to this one. The import dialog says "The people named in its history are not
  given access; their names stay in the history as former people." when the export brings a history (the upload answer's
  `with_history`), and "Nobody else is given access." otherwise.
- **Redaction.** Redacting the whole import takes the note away with the content and the file's name (D723); blanking in
  parts keeps it, since the person chose what to take away.

**What it is not.** The original's steps are not replayed (option (b)), and its chat does not become chat messages of
the new document. A hand-written export whose lines are not steps or messages does not refuse the import: a line that is
no object is nothing anybody did, a missing name is unknown, a missing time is none (`claudia_server/original_history.py`).
