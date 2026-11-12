---
id: D266
title: "Claude is a second provider behind the same `ai` user, reached with an API key set in the server settings"
status: current
applies-to: all
date: 2026-11-11
round: "The AI agent: rights, modes and proposals (E7)"
supersedes: []
superseded-by: []
---

# D266 · Claude is a second provider behind the same `ai` user, reached with an API key set in the server settings

**Claude takes the `ai` seat as a second provider next to the local model, chosen in the server settings (Scripted stand-in, Local model, Claude), using Anthropic's API with a key the administrator enters there.** Nothing else about the `ai` user changes: one per document, the same rights (D261), the same modes (D262), the same tools. The key is write-only: after saving it shows only its last four characters, it stays on the server in the private settings file, never reaches a document, a client or the log, and an operator can supply it as `ANTHROPIC_API_KEY` or a key file, which wins over the saved one (D154). The model name is a free text field with suggestions. Applying a change asks the provider one test question first and refuses it with the reason if that fails.

**Notes.** Needs the model interface widened (native tool use, system prompt, cancellation, errors that mean something) and a concurrency that is a property of the provider (local 1, Claude a small number), E7.3. Remote use is gated by D264. **Parked, not decided against:** Claude connecting *in* (a person's own Claude app attaching to the server, e.g. over MCP, with no API key on the server), which would conflict with D8 (the document server initiates) and is not a server setting. Screen: `notes/mockups/ai-settings-provider.svg`.
