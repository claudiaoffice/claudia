---
id: D532
title: "The front page shows a way back from a collection: "← All documents", Esc, and choosing the collection again"
status: current
applies-to: all
date: 2026-11-15
round: "Document handling on the front page (branch file-handling)"
supersedes: []
superseded-by: []
---

# D532 · The front page shows a way back from a collection: "← All documents", Esc, and choosing the collection again

**While a collection is shown the page says so and offers "← All documents" above the list; Esc (when no menu is open and nobody is typing) and choosing the collection again do the same; the shown collection's button says so in its tooltip; removing the shown collection returns to all documents. Before, choosing the shown collection again was the only way back and nothing said so.**

**Notes.** Reported by the owner, 2026-11-15. The logic is `nextShown` and `stillShown` in `web/app/lib/mine.ts`.
