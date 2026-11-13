---
id: D264
title: "A remote AI needs two opt-ins: the server's and each document's owners"
status: current
applies-to: all
date: 2026-11-11
round: "The AI agent: rights, modes and proposals (E7)"
supersedes: []
superseded-by: []
---

# D264 · A remote AI needs two opt-ins: the server's and each document's owners

**A remote AI provider (Claude, D266) may only see a document's content when two opt-ins are both given: the administrator's on the server, and the owners' in that document.** The server opt-in is a sentence the administrator confirms in the server settings ("Document content is sent to Anthropic when someone asks @ai"), recorded with who and when. The document opt-in is the owners' switch, **off by default**, in File ▸ Manage ▸ AI. Without both, `@ai` in that document uses the local model or the stand-in and says so. The `ai` user's row in the panel carries a badge naming the provider and whether it is remote ("Claude · remote", "Qwen2.5 · this server"), and every answer from a remote provider is marked as such.

**Notes.** The administrator is not the owner of the documents and cannot open sealed ones, yet enabling a remote provider would send their content out; so the administrator's consent alone is not enough. Builds on D32 (remote AI is an opt-in with a visible indicator). Anything the website or the help says about privacy has to mention that this option exists and is off until both opt-ins are given. Screen: `notes/mockups/ai-settings-provider.svg`.
