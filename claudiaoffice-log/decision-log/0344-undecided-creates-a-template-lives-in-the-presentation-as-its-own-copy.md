---
id: D344
title: "A template lives inside the presentation as its own copy; a template file is a source to copy from, and to pull an update from on request"
status: undecided
applies-to: creates
date: 2026-11-13
round: "Real-world documents: templates and layouts in creates (branch real-world-docs)"
supersedes: []
superseded-by: []
---

# D344 · A template lives inside the presentation as its own copy; a template file is a source to copy from, and to pull an update from on request

**Proposal.** A presentation holds its template as its own copy, so a document stays self-contained, private and
the same wherever it is opened. A template *file* (`.potx`, `.otp`, or a claudia presentation used as one) is a source
that File ▸ New copies from, and later a source to *pull* an update from when the author asks — the way embeds are
updated after asking (D72) — never a live link that changes slides by itself.

**Notes.** The alternative, templates kept on a server and referenced by every presentation that uses them, would make
a document depend on another one and on a server reading it, which D72 rules out for material between apps. An
organisation's house template (E12.7, public administration) is then a file people start from, not a shared object.
