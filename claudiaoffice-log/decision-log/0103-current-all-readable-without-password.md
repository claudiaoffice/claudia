---
id: D103
title: "Readable without a password"
status: current
applies-to: all
date: 2026-11-02
round: "Document container and encryption (seventeenth round)"
supersedes: []
superseded-by: []
---

# D103 · Readable without a password

**Readable without a password:** document id, title, app type, last change, size, unlisted flag, format version, KDF parameters. This is what the server's document list shows. Server access secret for list and create; creation otherwise only from loopback; unlisted flag as proposed under D53.

**Notes.** Settles the open details of D53. The title is readable by anyone holding the file; the owner chooses it knowing that.
