---
id: D753
title: "The core ends when its parent process is gone, besides when its link to Neutralino breaks"
status: current
applies-to: all
date: 2026-11-25
round: "The Windows installer, first real install (CODE-97; branch `win-installer-fix`)"
supersedes: []
superseded-by: []
---

# D753 · The core ends with the process that started it

**`core-entry.ts` looks every second (`watchParent`, `src/parent-watch.ts`) whether the process that started it (Neutralino)
is still there: its pid is alive (`kill(pid, 0)`) and still its parent. When it is not, the core logs
`its parent process <pid> is gone; ending`, lets go of its server like it does when the link breaks, and exits.** A start
with no parent to watch (pid 0 or 1) is not watched. The link to Neutralino still ends the core, as before.

**Why (measured).** The Windows install test of CI, on a window of composes that it killed outright (`Stop-Process -Force`,
what Task Manager's "End task" does to a window that hangs, and what a crash does), 2026-11-25, windows-2022: ninety
seconds later `node.exe` of the core was still running, with no line in `shell.log` about the link having broken. Neutralino
"doesn't send kill signals to extension processes" (its release notes for v4.0.0; issue 1567 there is open), so nothing else
ends it. A window that is *closed* leaves nothing: the same step closed one with `CloseMainWindow` and the core was gone
within 30 seconds.

**Alternatives.** A job object that ends the core with Neutralino (Windows only, in `claudia-start.exe`, which does not
start Neutralino: the node launcher does); a heartbeat over the link (needs Neutralino to answer, which is not known);
ending the core when stdin closes (Neutralino may close it right after sending the tokens: not known).

**Notes.** The cause of the link staying up is not known (a socket handle that the core or a child of Neutralino inherited is
the first suspect); this does not depend on it. A reused pid could keep a core alive: not guarded against. The server the
core started is not ended with it: it is shared and ends by itself ten minutes after its last window (D434).
`claudia-start.exe` stays, with its message box, when Neutralino was killed: its exit code is not 0, and that is what the
box is for.
