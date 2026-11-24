---
id: D750
title: "The shortcuts of the Windows install start claudia-start.exe: node without a console window, its output in a log file"
status: current
applies-to: all
date: 2026-11-24
round: "The Windows installer, first real install (UX-77; branch `win-installer-fix`)"
supersedes: []
superseded-by: []
---

# D750 · The shortcuts start `claudia-start.exe`, which hides node and keeps its output in a log

**Every shortcut and the post-install start of the Windows installer runs `{app}\client\claudia-start.exe <app>`, a small
C program (`packaging/windows/launcher/claudia-start.c`) of the GUI subsystem. It starts `node\node.exe client\bin\<app>.mjs`
(and any further options) with `CREATE_NO_WINDOW`, standard input from `NUL` and standard output and error in
`%LOCALAPPDATA%\Claudia\<app>\state\launcher.log` (the run before is kept as `launcher.log.old`), waits for it and returns its
exit code. If node stops with a code other than 0, a message box says so, with the path of the log and its last 1200
bytes.** The workflow builds it with MinGW `gcc -O2 -municode -mwindows` (`build.py launcher`), tries it in a folder laid
out like an installation (both streams in the log, options passed on, the old log kept), and stages it (`--launcher`).

**Why.** The shortcuts started `node.exe`, a console program: its window stayed for as long as the app ran, with nothing
in it but Neutralino's start-up lines (two errors about a missing `resources.neu` and `/favicon.ico`, and the note that
the core is started as a plain `node` when the path has a space). Minimising it (`runminimized`, D741) left a taskbar button.
The owner asked to hide it and to keep what it prints in a log.

**Alternatives.** A `.vbs` or PowerShell shim (`Run ..., 0`): no compiler, but a script host that antivirus tools dislike,
and no exit code or message box. `windowsHide` inside the Node launcher: node's own console is already there by then.
A job object to end the whole tree: the server is started `detached` and shared between apps on purpose (D445).

**Notes.** The program knows the layout of the installation (D741: `node\`, `client\bin\`), the same layout the Inno script
installs; a test holds the two together. It does not decide anything else: finding the app folder, the copy for the window
and the core's command stay in the Node launcher. Not verified on Windows: that no console flashes, and what happens when
the window is closed (whether node and the core end; if a `node.exe` is left in the task manager after closing an app, that
is a bug of its own, now invisible). Windows' SmartScreen and antivirus tools treat an unsigned small executable with
suspicion; signing (D744) covers the installer only.

**Known limits.** The run before is kept as `launcher.log.old` only if that file is not held open: the server outlives the window
and may have inherited the log's handle, and then Windows refuses the replacement; the log is then written over (a log,
without the run before). The message boxes of the program are in English: the program has no catalogue (the installer's
texts are Inno Setup's), so it does not yet follow the rule that every user-visible text is translated (coding standard
11); the three languages of the suite need a decision on how a C program gets them (the language of the installation, written
by the installer, is one way).
