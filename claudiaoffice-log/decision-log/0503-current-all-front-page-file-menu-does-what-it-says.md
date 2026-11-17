---
id: D503
title: "Proposal: on the front page, File ▸ New starts a new document's name and File ▸ Open… goes to the search over the list"
status: current
applies-to: all
date: 2026-11-15
round: "The three desktop clients: one server, files, printing (branch clients)"
supersedes: []
superseded-by: []
---

# D503 · Proposal: on the front page, File ▸ New starts a new document's name and File ▸ Open… goes to the search over the list

**Proposal: the short native menu of the front page (D447) keeps New, Open… and Open a File…, and each does something
the person sees. New empties the Document field, puts the cursor into it and marks the "start a new one" part of the
form (an iris line at its left, until the person opens, creates or picks another document). Open… puts the cursor into
the search field over the list, its text selected, scrolled into view. Open a File… shows the shell's Open dialog
(D501). Before a menu action reaches the page, the Neutralino shells give the frame the keyboard focus.**

**Notes.** Owner, 2026-11-15: the three did nothing in any client; they should get a function, or else not be shown.
They did run: New and Open… moved the focus, which a window whose page did not have the focus did not show, and Open a
File… clicked a file input from a script, which no web view allows without a click in the page. A New that creates a
document at once was not chosen: a new document needs a name, a person and a password first. To be confirmed by the
owner.

**Checked against the code, 2026-11-17 (`main` at `6814bac`).** Built as proposed: `OpenDialog.vue` (File ▸ New empties and marks the Document field, File ▸ Open… goes to the search over the list). The owner made the code the record of what is decided (log audit of 2026-11-17), so the status is current; replace it with a new decision to change it.
