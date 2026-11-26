---
id: D1628
title: "Uninstalling on macOS is an app that leaves only documents and settings"
status: current
applies-to: all
date: 2026-11-26
round: "E8.5 macOS installer, part 3: the package (branch `mac-installer`); designed 2026-11-25, built on Linux in CI by the owner's answers of 2026-11-26"
supersedes: []
superseded-by: []
---

# D1628 · Uninstalling on macOS is an app that leaves only documents and settings

**uninstall claudia** (`/Applications/Utilities`) says what it will do ("claudia's apps that are open, also those of
other people of this Mac, are closed."), asks macOS for an administrator's password and runs
`runtime/uninstall.sh` as root: it stops and removes the service and its account, ends every process of claudia by
what it runs (the windows, the cores, the servers; not itself), gives the shared folders to `root:admin`, removes the
apps, itself, the runtime, the service's log and each person's `~/Library/Caches/Claudia`, and makes macOS forget the
package. What is left: the shared documents (for the administrators to open; a file with more than one link is left
as it is) and each person's own folder (`~/Library/Application Support/Claudia`, her documents and settings) and her
logs; its last words say where, in English or German as the Mac's first language is. A step that fails is named, and
claudia is not said to be removed. Nothing is followed through a link a person made.

**Why a script app, not an AppleScript applet:** the package is built on Linux, which has no `osacompile` (the owner,
2026-11-26); `osascript` asks for the password the same way.
