---
id: D505
title: "The Linux window takes a file dropped on the front page and hands it to the page (offer_file)"
status: current
applies-to: all
date: 2026-11-15
round: "The three desktop clients: one server, files, printing (branch clients)"
supersedes: []
superseded-by: []
---

# D505 · The Linux window takes a file dropped on the front page and hands it to the page (offer_file)

**WebKitGTK does not give the page a file dragged in from the file manager, so the GTK window takes it itself: a drop
target on the whole window (capture phase, `Gdk.FileList`) accepts files only while the front page is shown, reads
the first file (up to 100 MB) and sends it to the page as `offer_file` {request, name, size}, followed by the same
`file_chunk`/`file_done` pieces a picked file uses (D501). The front page treats it like a file dropped into its own
drop area: it imports it, or says that this window's app does not open it. Shell contract v1 gains `offer_file`
(shell → page); a page that does not know it ignores it. In a document window nothing is taken.**

**Notes.** Owner, 2026-11-15: dragging a file from the Finder onto the start page imports it on the Mac; on Linux
nothing happened; he asked to make it work. On macOS and Windows the web view hands the drop to the page, so the
Neutralino shells need nothing. Only the first of several dropped files is taken, like the page's own drop area.
