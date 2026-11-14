---
id: D444
title: "A desktop window shows its own app only: its front page lists that app's documents and refuses other kinds of file"
status: current
applies-to: all
date: 2026-11-14
round: "One server for all three apps (branch one-server)"
supersedes: []
superseded-by: []
---

# D444 · A desktop window shows its own app only: its front page lists that app's documents and refuses other kinds of file

**Clicking Claudia Composes on the desktop gives Composes, even though the server behind it hosts all three apps. The
shell says which app its window is (`welcome.app`, an optional field of contract v1), and the front page then shows
that app's documents only — in the place's list, in Mine and in collections — with no app filter and no choice of
kind for a new document. Open a File… offers only that app's formats (Composes: DOCX, ODT and Claudia texts), and a
file of another kind is refused however it arrives (picker, dropping, a Claudia file of another app), with a message
that names the app it belongs to. In a browser tab the front page stays as D443 has it: every app, with the filter.**

**Notes.** Owner, 2026-11-14. The alternative — a window that turns into whichever app its document is, menus and
all — was put to the owner and not taken: a person who starts Composes expects Composes. A shell that does not send
`welcome.app` (one from before this patch) gets the browser's page; such a shell also starts a server of one app, so
the page has only that app's documents anyway. Handing a refused file to the right app ("Open it in Claudia
Computes") needs the file's path, which a page never has; it is for the shells to add if wanted.
