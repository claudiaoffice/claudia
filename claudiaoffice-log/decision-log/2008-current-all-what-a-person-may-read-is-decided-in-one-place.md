---
id: D2008
title: "What a person may read of the chat and the history is decided in one place, which every way out asks"
status: current
applies-to: all
date: 2026-11-25
round: "Bug eater, batch 5 (branch batch-5): SEC-24, SEC-26, SEC-22"
supersedes: []
superseded-by: []
---

# D2008 · What a person may read of the chat and the history is decided in one place, which every way out asks

**Decided 2026-11-25** by the owner (architecture review of 2026-11-25, candidate "one reader's view").

D1261 says which parts a role holds the keys of (a viewer: the content only). What one person may read beyond her role
was written out at each way out of a document: a private chat message is for its sender and its recipient, in the chat
log, in the redaction of chat messages and in the live push. The owner's export with history forgot it and carried the
private messages between other people (SEC-24). An office export dated the file from the history, so a viewer's odt or
docx said who made and changed the document and when, which her role may not read (SEC-26).

**Rule.** `Reader` (`claudia_server/audience.py`), one person as what she may read: `holds(part)`, `reads(message)`,
`chat(messages)` and `log(document)`, the history or an empty one for a role without its key. Every way out asks it: the
chat log, the message numbers of a redaction, the live push of a message, the export with history, and the office
exports of composes, computes and creates.

- An owner's export with history holds the messages for everybody and the private ones she sent or received.
- An office export made by a person whose role does not hold the history says neither who made or last changed the
  document nor when; an open suggestion keeps who made it and is dated with the time of the export (an OpenDocument
  tracked change needs a date). Owners and editors export as before (D411).
- Who wrote which stretch of a text is content (SEC-22, note in D1261), so it is not the reader's to hold back.

**Notes.** A picture's local path was the third rule of this kind; it is not one any more (D2009: the person decides,
and a kept path is for everybody who can open the document).
