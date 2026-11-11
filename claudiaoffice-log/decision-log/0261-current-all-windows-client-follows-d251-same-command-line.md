---
id: D261
title: "The Windows client follows D251 and matches the Linux and macOS clients: three apps, the same command line, the same server flow"
status: current
applies-to: all
date: 2026-11-11
round: "E5.11 Windows client: three apps, command line, server flow (branch `win-client-complete`)"
supersedes: []
superseded-by: []
---

# D261 · The Windows client follows D251 and matches the Linux and macOS clients: three apps, the same command line, the same server flow

**`clients/windows` is built the way D251 describes (Neutralino's own shell page, the web app framed in it, a Node extension for the native parts), it runs all three apps (composes, computes, creates; a window is one app, D242), and it has the same command line as Linux and macOS: `claudia-<app> [--server URL] [--debug]`, also as `node dist\launch.js <app> …` and `start-win-client.cmd [composes|computes|creates] [--server URL] [--debug]`.** The server flow is the one of D241–D248: a window connects only to servers of its own app, https by default and plain http only for this computer, the shell owns the server list (`shell.json`, same format as Linux), certificates must come from an authority this computer trusts (Node reads the Windows certificate store with `--use-system-ca`; self-signed certificates wait for D245). The Windows `.cmd` file is the only difference in the launch interface; parameters and their meaning are identical.

**Notes.** *Origin:* the owner's request of 2026-11-11 ("extend the functionalities … to the windows client as well", "the parameters should work the same"). It carries out what D251 left as a follow-up for Windows and replaces the D159 injection path in `clients/windows` (D159 was already superseded by D251; nothing new to supersede). *What stays Windows' own:* no application-menu relocation and no Cocoa roles in the menu (D44, D158), no file-dialog workaround until WebView2 shows it is needed (D216), `%LOCALAPPDATA%\Claudia\<app>\{documents,state}` and `.venv\Scripts\python.exe`, the extension command in Neutralino's `commandWindows`, and the process-tree stop of D262. *Shared with macOS, byte for byte:* `web/app/lib/shell-bridge.ts` (`detectParentSink`), its tests, the shell contract README and D251 itself, so the two branches merge without a second version of the web side. *Unverified:* nothing of this has run in a real Neutralino window on Windows; the README of `clients/windows` lists what is open.
