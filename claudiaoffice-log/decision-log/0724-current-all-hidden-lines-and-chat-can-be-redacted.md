---
id: D724
title: "Steps on hidden lines and chat messages can be redacted"
status: current
applies-to: all
date: 2026-11-16
round: "The redaction contract (D229), 2026-11-16"
supersedes: [D229]
superseded-by: []
---

# D724 · Steps on hidden lines and chat messages can be redacted

**Steps on hidden lines and chat messages can be redacted.** A step that a restore left on a hidden line is redacted
like one on the active line (part of what D235 asked). A chat message is redacted by number: it keeps its number,
author, recipient, time and place and loses its words (`ChatRecord.redacted`); the `redacted` event names the messages.

**Notes.** Without this, a secret that only lived on a hidden line or was pasted into the chat could not be removed.
The other side effects in D235 (viewers and hidden lines, chat after a restore, the AI after a restore) stay open.
