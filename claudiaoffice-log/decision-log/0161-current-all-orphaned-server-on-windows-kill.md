---
id: D161
title: "Proposal: an orphaned `claudia_server` on a hard-killed Windows shell is a known open issue for this first version, not something E5.11 builds a fix for"
status: current
applies-to: all
date: 2026-11-08
round: "Neutralino on Windows and macOS (twenty-eighth round)"
supersedes: []
superseded-by: []
---

# D161 · Proposal: an orphaned `claudia_server` on a hard-killed Windows shell is a known open issue for this first version, not something E5.11 builds a fix for

**Proposal: an orphaned `claudia_server` on a hard-killed Windows shell is a known open issue for this first version, not something E5.11 builds a fix for.** Windows has no POSIX process groups and no real `SIGTERM` (Node's `ChildProcess.kill()` always terminates outright there, per Node's own docs), so `server.ts`'s `stop()` already has only one hard step even in its normal path — this decision is specifically about the *abnormal* case, the shell process itself being killed outright rather than closed, which leaves the server with no shutdown signal of any kind. The owner chose (`AskUserQuestion`, 2026-11-08) to match macOS's own precedent — flag it as a known gap in the README's "Not done" — rather than build a Windows Job Object (or an equivalent job-object-based cleanup mechanism) now.

**Notes.** Mirrors the gap `server.ts`'s own top comment already flags for macOS ("the shell itself is killed outright... not solved here either"), just arriving one step earlier on Windows since even the ordinary stop path has no softer signal. Revisit if this turns out to matter in practice (orphaned `claudia_server` processes accumulating after killed sessions).

*Written as a proposal; confirmed by the owner on 2026-11-10, since the code already follows it.*
