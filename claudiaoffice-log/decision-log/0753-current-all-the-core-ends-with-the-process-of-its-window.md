---
id: D753
title: "The core ends when the process of its window is gone, besides when its link to Neutralino breaks"
status: current
applies-to: all
date: 2026-11-25
round: "The Windows installer, first real install (CODE-97; branch `win-installer-fix`)"
supersedes: []
superseded-by: []
---

# D753 · The core ends with the process of its window

**The page tells the core which process the window is (`NL_PID`, a global of Neutralino's client library) in its `start`
request (`windowPid`); `core-entry.ts` then looks every second (`watchProcess`, `src/parent-watch.ts`) whether that pid is
still there (`kill(pid, 0)`). When it is not, the core logs `the process <pid> is gone; ending`, lets go of its server like
it does when the link breaks, and exits.** It also watches the process that started it (`watchParent`: alive and still its
parent), which is the window on a Mac and Linux. A pid of 0 or 1 is not watched. The link to Neutralino still ends the core,
as before.

**Why (measured).** The Windows install test of CI, on a window of composes that it killed outright (`Stop-Process -Force`,
what Task Manager's "End task" does to a window that hangs, and what a crash does), 2026-11-25, windows-2022: ninety
seconds later `node.exe` of the core was still running, with no line in `shell.log` about the link having broken. Neutralino
"doesn't send kill signals to extension processes" (its release notes for v4.0.0; issue 1567 there is open), so nothing else
ends it. A window that is *closed* leaves nothing: the same step closed one with `CloseMainWindow` and the core was gone
within 30 seconds.

**First try, and why it was not enough (measured).** Watching only the parent of the core failed on the same CI step: on
Windows the core's parent is not Neutralino (core 7876 had parent 7260, Neutralino was 6812; for the closed window: core
2148, parent 6872, Neutralino 8016), probably a shell that outlives Neutralino and may have kept the link's socket handle
open, so the parent was never gone. The page's `NL_PID` is Neutralino's own pid.

**Alternatives.** A job object that ends the core with Neutralino (Windows only, in `claudia-start.exe`, which does not
start Neutralino: the node launcher does); a heartbeat over the link (needs Neutralino to answer, which is not known);
ending the core when stdin closes (Neutralino may close it right after sending the tokens: not known).

**Notes.** The cause of the link staying up is not known (a socket handle that the core or a child of Neutralino inherited is
the first suspect); this does not depend on it. A reused pid could keep a core alive: not guarded against. A window killed before its page has sent `start` (the first second or two) leaves a core that knows no window pid: seen once in CI, not guarded against (the CI step now waits for the page). An older page that does not send `windowPid` leaves the parent watch and the link as before. The server the
core started is not ended with it: it is shared and ends by itself ten minutes after its last window (D434).
`claudia-start.exe` stays, with its message box, when Neutralino was killed: its exit code is not 0, and that is what the
box is for.
