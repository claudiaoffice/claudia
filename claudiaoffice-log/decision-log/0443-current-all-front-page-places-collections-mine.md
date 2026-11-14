---
id: D443
title: "The front page: My places, Collections, Mine on top, search, Open a File…; File ▸ Open is the same page in a dialog"
status: current
applies-to: all
date: 2026-11-14
round: "Opening files from the computer (branch one-server)"
supersedes: []
superseded-by: []
---

# D443 · The front page: My places, Collections, Mine on top, search, Open a File…; File ▸ Open is the same page in a dialog

**The front page (sheet 10, A) keeps today's list of servers on the left as "My places" (a server on this computer is
called "This computer") and adds "Collections". The middle has a search over Mine and the place shown (ids only:
contents are sealed), "Open a File…" (Ctrl+Shift+O, and dropping a file anywhere), Mine on top — the documents opened
before, on any place — and then every app's documents of the place, with an app filter. A new document asks for its
kind every time on a server of several apps (on a server of one app there is nothing to ask). File ▸ Open… (Ctrl+O) in
a document shows the same page in a dialog; the document opened there replaces the one in the window. File ▸ Open a
File… opens the file picker at once. In a browser tab Claudia's keys win over the browser's. Mine and the collections
are kept in the browser (`localStorage`, per origin) until the vault exists.**

**Notes.** Owner, 2026-11-14: Mine at the top; Create always asks; the app's shortcuts win. Sheet 10 drew File ▸ Open
as opening "in a new window"; a new browser window cannot take over the login of this one, so the person would type
the password twice. Replacing the document in the window, as every office suite's File ▸ Open does, is what was
built; a new window remains possible later. The file goes to the place the page is on (a page talks only to its own
server, D170); to put it elsewhere, open that place first. The desktop shells will keep Mine in `shell.json` in their
own patches.
