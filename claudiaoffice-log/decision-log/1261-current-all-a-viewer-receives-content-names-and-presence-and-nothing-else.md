---
id: D1261
title: "A viewer's connection receives content, names and presence, and nothing else"
status: current
applies-to: all
date: 2026-11-19
round: "The document container and its security, second round (branch e2-document-sec)"
supersedes: []
superseded-by: []
---

# D1261 · A viewer's connection receives content, names and presence, and nothing else

**Decided by the owner 2026-11-19 (accepted the proposal). Not built.** What the file already withholds from a viewer
(D101: the content key only), the live session withholds too (E2.4, SEC-17). A viewer's connection gets:

- the document's content and its changes as the apps send them, **without who made them, when, why or how it was
  labelled**; the `command` event reaches a viewer as the revision alone;
- the names of the people in the document (D111) and presence: who is here and where their cursor is;
- nothing from the history (log, checkpoints, lines, restore proposals, "returned to" notices, the data behind "show who
  wrote what", E9.10) and nothing from the chat, public or private. A viewer cannot post chat today either.

**How it is made so that it stays so.**

- Every kind of event is listed once with the domain it belongs to (`content`, `history`, `chat`). An event kind that is
  not in the list goes to owners and editors only, so a new event can leak nothing by being forgotten.
- Every protocol method says which domain it reads (`reads="history"`, `reads="chat"`; `content` is the default for what
  only reads the document). A viewer who calls one that reads another domain is refused with `forbidden`. A test goes
  through every registered method and fails for one that does not state it.
- `welcome` leaves out for a viewer what comes from the history.
- The AI answering a viewer reads content only (D261): the document lens for a question asked by a viewer holds no
  history and no chat.
- The history and chat panel shows a viewer one sentence instead: "History and chat are for the document's editors."

**Notes.** Closes SEC-17 and the live half of E2.4, and with it the "weaker than it reads" part of E7.4. Whether a viewer
may see the document's public chat was a product question; the owner accepted "no", the same as the file.

**2026-11-25 (SEC-22, owner):** who wrote which stretch of a text (the `runs` of a paragraph) is content, not history: a
viewer receives it live and in her own file, as a reader of a paper sees the handwriting. What she does not receive is
when anybody wrote it, or who changed the document when; an office export a viewer makes says neither (SEC-26, D2008).
Guarded by `test_a_viewer_receives_who_wrote_which_words_as_part_of_the_content`.
