---
id: D1494
title: "The menu Config is called Preferences in all apps and clients and has the entry AI…"
status: current
applies-to: all
date: 2026-11-22
round: "E7.11 Claude as an AI provider (branch e7-11-claude-provider)"
supersedes: []
superseded-by: []
---

# D1494 · The menu Config is called Preferences in all apps and clients and has the entry AI…

**Decided 2026-11-22 (settles To decide #3 and amends where D264 put the dialog).**

- "Config" is renamed "Preferences" in the web app, the Linux shell and the Neutralino menus (Windows and macOS). Action ids stay `config.*`
  so the shell contract does not break.
- New entry "AI…" (`config.ai`) opens the dialog "AI in this document". Editors and viewers open it read-only; only the owners
  change it. A consent change shows a muted line in History & Chat, in the design of the export, print and PDF lines.
- **Key: Ctrl+Shift+Alt+E, provisional.** The owner asked for Ctrl+Shift+Alt+H, but H is Present from This Slide in the shared
  manifest, and the Linux test rejects a shared chord. E was the only free Ctrl+Shift+Alt letter. **The owner decides.**
