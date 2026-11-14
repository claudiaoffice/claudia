---
id: D392
title: "The administrator's tool registry and the plugins are two separate things"
status: current
applies-to: all
date: 2026-11-13
round: "Rendered text containers (branch containers)"
supersedes: []
superseded-by: []
---

# D392 · The administrator's tool registry and the plugins are two separate things

**A *tool* is a program the administrator registered under a logical name (`typst`, `mmdc`, as for LaTeX in D98); a *plugin* is a manifest that names the logical tools it needs. A plugin can use only registered tools.** `ToolRegistry` resolves lazily, never remembers a failure, checks the version and gives each tool an identity (name, version, digest of its options) that goes into the cache key and the note of what made a picture.

**Notes.** The owner chose this ("the safer variant") over plugins that bring their own programs. Installing a tool later needs no restart. The registry reads the typeset settings once at start-up, so an administrator who changes them while the server runs needs a restart (follow-up).
