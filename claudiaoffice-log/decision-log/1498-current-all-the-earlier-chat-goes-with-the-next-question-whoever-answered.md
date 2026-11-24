---
id: D1498
title: "The earlier chat goes with the next question, whoever answered it"
status: current
applies-to: all
date: 2026-11-22
round: "E7.11 Claude as an AI provider (branch e7-11-claude-provider)"
supersedes: []
superseded-by: []
---

# D1498 · The earlier chat goes with the next question, whoever answered it

**Decided 2026-11-22.** One `ConversationMemory` is shared by all providers of a document, so "and why is that?" after the
local model answered goes to Claude with the earlier question and answer, once the owners allow Claude. The dialog tells
the owners what Anthropic is sent: the question and the earlier chat between the person who asks and the ai, and the parts of the
document the ai looks at to answer her. Documents are encrypted on the server; Claude reads what it is shown in plain text.
