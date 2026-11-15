---
id: D530
title: "A document's description and tags are plain properties of the file, changed by editors and owners, not part of the history"
status: current
applies-to: all
date: 2026-11-15
round: "Document handling on the front page (branch file-handling)"
supersedes: []
superseded-by: []
---

# D530 · A document's description and tags are plain properties of the file, changed by editors and owners, not part of the history

**A document has an optional description (Markdown, at most 2000 characters) and optional tags (at most 10, each at most 30 characters, lower case, no commas). Both are kept in the plain `manifest.json` of the document file next to the name, uid and app (D103, D533): they are not encrypted, anybody who may list the server reads and searches them without a password, and they are not a command of the document, so they are not in its history and not undone with it. Only an editor or an owner changes them, with their own password (`set_details`, like delete, D141); a viewer does not (amended 2026-11-15, owner: "only editors should be able to change description or tags"). The list (`GET /api/docs`) carries `description` and `tags` for every document. The front page shows a line of the description and the tags as chips, narrows by a tag, and searches both; Details… on a row edits them without opening the document.**

**Notes.** Owner, 2026-11-15: "a document property in the file, but not encrypted so it can be read by anyone with access to the server." The mock-up (sheet 10 follow-up) drew the change as a logged command `SetDetails` so that it shows in the history; this was not built, because the plain manifest is what the owner asked for and a value that must be readable without keys cannot also live only in a sealed log. The manifest is not authenticated (D103): somebody who can write the file can change the description as they can the title; the decision records this rather than hiding it. The description is shown as inline Markdown only, read by the same small reader as the speaker notes (D347): no HTML, no pictures, links are shown and not followed. A tag change is not announced to the sealed history; `details_changed` is sent to the people connected. Editors may edit too (amended). Whether the front page may show Details to viewers read-only is open: the list does not know who anybody is (D103), so the dialog is offered on every row and the server refuses with a sentence.
