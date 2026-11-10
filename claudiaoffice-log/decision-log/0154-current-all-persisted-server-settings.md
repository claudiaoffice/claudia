---
id: D154
title: "Persisted server settings (how many documents, the access secret, the AI model and device, the LaTeX program paths) follow an operator-override precedence:…"
status: current
applies-to: all
date: 2026-11-07
round: "Server administrators and settings (twenty-seventh round)"
supersedes: []
superseded-by: []
---

# D154 · Persisted server settings (how many documents, the access secret, the AI model and device, the LaTeX program paths) follow an operator-override precedence:…

**Persisted server settings (how many documents, the access secret, the AI model and device, the LaTeX program paths) follow an operator-override precedence: an explicit command-line or environment value is used for that run and is never written back to the settings file; absent it, the persisted value applies; absent that, the built-in default does.** The access secret itself is kept in the clear in the private settings file, not hashed — unlike a password, it must be recoverable so a settings dialog can reveal it, not just rotate it.

**Notes.** Protects an operator's deployment config (a container's env vars, a systemd unit's flags) from being silently overridden by whatever the last person to use the settings UI clicked — and protects the settings UI symmetrically, since its own choice always survives a restart once no CLI value contradicts it.
