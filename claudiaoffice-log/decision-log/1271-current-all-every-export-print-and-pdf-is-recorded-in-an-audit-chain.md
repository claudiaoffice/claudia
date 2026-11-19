---
id: D1271
title: "Every export, print and PDF is recorded, in an audit chain under the history key"
status: current
applies-to: all
date: 2026-11-19
round: "The document container and its security, second round (branch e2-document-sec)"
supersedes: []
superseded-by: []
---

# D1271 · Every export, print and PDF is recorded, in an audit chain under the history key

**Decided by the owner 2026-11-19: the proposal, widened to printing and PDF "as that indicates data leakage"; and the record
is not redactable, not by an owner either. Not built.**
D108 says every unencrypted export is logged. This makes it one rule: **whatever leaves the document in a form someone can
read outside Claudia is recorded** — an export in any format (Claudia unencrypted, Word, Excel, PowerPoint, OpenDocument),
a print, and a PDF.

- **What is recorded:** who, when, what kind (export, print, PDF), the format, and which parts (content; history and chat
  for owners). For a print or a PDF, the document's pages, not what was on them.
- **Where.** A chain of blocks of its own, sealed with the history key, next to the history and the chat. Owners and editors
  read it; a viewer does not (D1261). It is not part of the command log, so it adds no revision and no undo step.
  Owners and editors see it in the History & Chat panel as a muted row ("Anna exported the document as Word").
- **The server writes it for the one who acts**, also for a viewer, who cannot write to the document.
- **Reliability is not the same for all.** The server makes an export itself and records it itself. A print and a PDF are
  made by the browser or by the desktop shell (the layout library runs there), so the client reports them and the server
  records the report: a record of what Claudia's own screens did, not a guarantee. The report is made when the file is
  saved or the page sent to the printer, not when the preview opens.
- **What it cannot see** is said in the help: copying from the screen, a screenshot, and the browser's or the operating
  system's own "print to PDF" outside Claudia's preview.
- **Not redactable, by anyone** (the owner, 2026-11-19: "not redactable, not by owner"): an owner could otherwise erase the
  trace of what she took out. The redaction contract (D720 to D726) does not reach the chain, and neither does the
  journal rewrite or a restore: a test fails if a redaction changes one byte of it. Only deleting the whole document
  removes it.

**Notes.** The first design had the record as a kernel entry or a history record, to be decided while building. A kernel
entry would add a revision and an undo step for something that changes nothing in the document, so the chain is the
choice.
