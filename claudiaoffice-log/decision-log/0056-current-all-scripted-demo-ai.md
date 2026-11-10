---
id: D56
title: "The demo's AI is a scripted stand-in"
status: current
applies-to: all
date: 2026-11-02
round: "Demo v0 (ninth round)"
supersedes: []
superseded-by: []
---

# D56 · The demo's AI is a scripted stand-in

**The demo's AI is a scripted stand-in** behind the pluggable `Engine` interface. It is a real participant: a connection named `ai`, one per document, it hears `@ai`, answers privately, shows a cursor and a typing indicator, and edits through the same method table as everybody, so locks and roles apply to it (D47).

**Notes.** The real model replaces the engine without client changes. The remote boundary of D8 is not built.
