---
id: D447
title: "On the front page the desktop apps' native menu has only what works there; a document gets the whole menu"
status: current
applies-to: all
date: 2026-11-14
round: "One server for all three apps (branch one-server)"
supersedes: []
superseded-by: []
---

# D447 · On the front page the desktop apps' native menu has only what works there; a document gets the whole menu

**A page says in its hello what it is (`view: "start"` or `"document"`, an optional field of contract v1). On the front
page the shells show File (New, Open…, Open a File…, Quit), View (Dark Mode), Config (App Language) and Help (About);
Edit, Format and Tools are not shown at all, rather than greyed out, and the other actions are switched off so their
keys do nothing either. On a Mac, Edit keeps Cut, Copy and Paste: their Cocoa roles are what makes the keys work in
the page's text fields. A document's hello brings the whole menu back; a page that does not say gets the whole menu,
as before. The manifest marks the front page's entries (`manifest.on_start`), so the three shells use one list.**

**Notes.** Owner, 2026-11-14, on sheet 11: Edit ▸ Cut on the front page makes no sense; How Do I…?, Documentation and
Ask ai open in a document's side panel today, so the front page's Help has only About. Found on the way: the front page
let Create run before it knew the server's apps, so a quick click on a server of one app asked for a kind (the Linux
shell's end-to-end test did exactly that); Create now waits for the list.
