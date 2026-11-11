---
id: D261
title: "The AI acts with the rights of the person who asked it"
status: current
applies-to: all
date: 2026-11-11
round: "The AI agent: rights, modes and proposals (E7)"
supersedes: []
superseded-by: []
---

# D261 · The AI acts with the rights of the person who asked it

**The AI acts with the rights of the person who asked it.** What it may read and write while answering a request is its own allow-list limited by the asker's role, checked at dispatch, and never more than the asker could do by hand. Each request runs under its own effective account, so the history says "ai, on behalf of X". One AI answer is one undo unit, and the asker can undo it with a single action ("undo the AI's last answer"), although the AI itself may not call `undo`.

**Notes.** Settles the first clause of D231 (where the AI's permissions come from: the intersection, E7.4). Its other clauses (fairness, cancellation and queue visibility in the AI server, structured output for small local models) stay open. Builds on SEC-10, which already checks the allow-list at dispatch; what is new is that the account is per request, not one fixed account per app. **Weaker than it reads until E2.4 lands:** the live server still sends connected viewers every command, history entry and chat message, so limiting what the AI reads protects less than it should, for the AI and for people alike. The same per-request account carries D262's mode.
