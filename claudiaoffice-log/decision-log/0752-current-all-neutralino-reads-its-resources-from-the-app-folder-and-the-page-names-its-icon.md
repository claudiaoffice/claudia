---
id: D752
title: "Neutralino is started with --res-mode=directory, and the shell page names its icon, so a start logs no resource errors"
status: current
applies-to: all
date: 2026-11-25
round: "The Windows installer, first real install (CODE-96; branch `win-installer-fix`)"
supersedes: []
superseded-by: []
---

# D752 · Neutralino reads its resources from the app folder; the page names its icon

**`buildShellCommand` passes `--res-mode=directory` besides `--path=<app folder>`, and the shell page template has
`<link rel="icon" href="/icon.png">`.** Both clients, Windows and macOS: the option is Neutralino's own since v6.3.0 (the
clients use 6.8).

**Why.** The launcher's log of a start (UX-82, D750) showed two errors of Neutralino on every start: `NE_RS_TREEGER`
(the resource tree, looked for in the binary and in a `resources.neu` that an app folder served from files never has) and
`NE_RS_UNBLDRE` (the web view asked the server for `/favicon.ico`, which the app folder does not hold). Nothing failed; the
log said "error" twice on a working start, which makes a real error hard to see.

**Alternatives.** A `resources.neu` (a build step and a file for nothing: the page is served from the folder, and the
launcher copies that folder); a `favicon.ico` file (a second icon format next to `icon.png`, which the window uses already).

**Notes.** Not run on Windows or on a Mac with the real Neutralino: the cause of `NE_RS_TREEGER` is read from Neutralino's
documentation (resource modes), not measured. The CI step that starts a window prints the start's log; if an error is still
there, this decision is wrong about it.
