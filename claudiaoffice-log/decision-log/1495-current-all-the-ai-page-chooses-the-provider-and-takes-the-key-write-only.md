---
id: D1495
title: "The administrator's AI page chooses the provider, takes the key write-only and tests before applying"
status: current
applies-to: all
date: 2026-11-22
round: "E7.11 Claude as an AI provider (branch e7-11-claude-provider)"
supersedes: []
superseded-by: []
---

# D1495 · The administrator's AI page chooses the provider, takes the key write-only and tests before applying

**Decided 2026-11-22; amends the thin slice of D266.**

- Three providers: scripted stand-in, local model, Claude. The settings of a provider that is not chosen are kept.
- The key is never shown again, only its last four characters. A key given by the operator (file or `ANTHROPIC_API_KEY`) wins and is never saved (D154).
- Apply asks Claude one test question first; a refused key never becomes the saved setting, and the page says why.
- The administrator confirms "Document content is sent to Anthropic when someone asks @ai." once; it is recorded with who and when,
  and asked again only when switching to Claude from another provider.
- Removing the key while Claude is chosen asks first and falls back to the local model.
- Anthropic's address is a hidden command-line option for the end-to-end tests, never a field of a page.
- No new dependency for HTTP: the standard library behind a seam.
