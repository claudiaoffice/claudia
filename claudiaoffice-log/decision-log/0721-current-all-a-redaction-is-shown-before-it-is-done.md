---
id: D721
title: "A redaction is worked out and shown before it is done, and may change what people see now"
status: current
applies-to: all
date: 2026-11-16
round: "The redaction contract (D229), 2026-11-16"
supersedes: [D229]
superseded-by: []
---

# D721 · A redaction is worked out and shown before it is done, and may change what people see now

**A redaction is worked out and shown before it is done, and it may change what the document looks like now.** The
kernel makes a plan first (`Document.plan_redaction`): the steps that are blanked, the chat messages, whether the
document as people see it changes, and that state. The client shows it, with the places that will turn into `█`, and
only a confirmed plan is carried out. A plan made against a document that changed since is refused.

**Notes.** The owner chose this over "refuse until the content is deleted from the current document first" (2026-11-16):
one step instead of two, and the preview makes the change visible before it happens. When the content is no longer in
the document, nothing anyone sees changes and the preview says so.
