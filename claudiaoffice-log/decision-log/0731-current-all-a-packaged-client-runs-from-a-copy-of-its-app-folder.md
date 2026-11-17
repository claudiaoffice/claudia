---
id: D731
title: "A packaged client runs from a copy of its app folder, with its own Node"
status: current
applies-to: all
date: 2026-11-17
round: "The Windows installer (E8.1; branch `win-installer`)"
supersedes: []
superseded-by: []
---

# D731 · A packaged client runs from a copy of its app folder, with its own Node

**The installed client is the checkout's client with a marker.** `clients/neutralino/packaged.json` (written by the
installer's build) says where the installer put the web frontend and the server, relative to the client's folder. With it
the launcher (`src/packaged.ts`, `src/launch.ts`)

* hands `CLAUDIA_WEB_DIR` and `CLAUDIA_SERVER_EXE` to the core, unless the person set their own server or frontend;
* runs the window from a copy of the app's folder in the person's own folder (`<claudia folder>\run\<app>`, made afresh at
  every start, without `bin/`), because the launcher writes the core's command into `neutralino.config.json` for the run and
  an installation in `Program Files` is read-only for a person without administrator rights;
* uses the 8.3 short name of the folder it runs from when the path has a space (`C:\Users\Max Muster\...`), as it did for node;
  without a short name it says so and names `LOCALAPPDATA` as the way to move it. A checkout in a folder with a space profits
  from the same rule.

The installer carries its own Node.js (`node\node.exe`, from the build's Node 22, which knows `--use-system-ca`): the core is a
Node program, and nobody should have to install Node to use the suite. Shortcuts start `node.exe client\bin\<app>.mjs`.

**Notes.** Known and accepted for now: each start shows a minimised console window of node, because nothing in it needs
reading (an own launcher without a console window is the way out; follow-up). The installed files are never changed by a run.
No file associations are registered: the apps take no file on their command line yet (they open files through the contract's
`pick_file`); that belongs with the import work and a decision of its own.
