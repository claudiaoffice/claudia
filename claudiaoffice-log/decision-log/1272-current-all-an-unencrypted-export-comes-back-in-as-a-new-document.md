---
id: D1272
title: "An unencrypted export comes back in as a new document, and its authors become names without accounts"
status: current
applies-to: all
date: 2026-11-19
round: "The document container and its security, second round (branch e2-document-sec)"
supersedes: []
superseded-by: []
---

# D1272 · An unencrypted export comes back in as a new document, and its authors become names without accounts

**Decided by the owner 2026-11-19 (accepted the proposal). Not built.**

- **Where.** Open ▸ Import from disk…, which already takes Word, Excel, PowerPoint, OpenDocument and sealed Claudia files
  (D438 to D442). It recognises the zip of D1270 by its first entry and says "A Claudia export" in the dialog.
- **Who.** The person who imports becomes the document's only owner and chooses the password, as for any new document. No
  slot, role or name from the file is taken over: the file has none.
- **What it makes.** A new document with a new uid (D533 to D536). Replaying the imported log gives the identical state; a
  test compares the two. A file with content only gives a document with a history of one step, the import itself.
- **Authors.** If the file brings history or chat, the names in it stay as *text* in those entries, marked as people who are
  not in this document ("former"). They are not accounts, hold no keys and are not shown in presence or in the people list;
  the name `ai` stays the AI (D1261, D261). Only owners and editors of the new document ever see them (D1261).
- **Refusals.** A file that is not a Claudia export, one whose parts do not fit its `export.json`, or one that breaks a
  reader limit (D104, E2.1) is refused with a sentence; nothing is made.

**Notes.** D102 keeps names out of the file for outsiders; an export is a file the owner chose to make readable, so names
in an owner's history export are part of what she chose.
