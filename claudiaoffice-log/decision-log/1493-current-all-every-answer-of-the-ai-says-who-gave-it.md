---
id: D1493
title: "Every answer of the ai says who gave it: ChatRecord.via, the badge and the answered-by line"
status: current
applies-to: all
date: 2026-11-22
round: "E7.11 Claude as an AI provider (branch e7-11-claude-provider)"
supersedes: []
superseded-by: []
---

# D1493 · Every answer of the ai says who gave it: ChatRecord.via, the badge and the answered-by line

**Decided 2026-11-22.**

The chat record of an `@ai` message carries an optional `via` (`provider`, `label`, `remote`, `note`); old chats have none.
The History & Chat panel shows a badge in words ("Claude · remote", "Qwen2.5-7B · this server": never by colour alone, BITV)
and under each answer "answered by …". The `note` is an English sentence on the wire; the web page says it in the person's
language by a catalogue. The text of the ai's message itself stays as the assistant wrote it (English, like its other
sentences).
