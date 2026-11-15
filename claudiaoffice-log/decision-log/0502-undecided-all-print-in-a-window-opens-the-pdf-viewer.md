---
id: D502
title: "Proposal: Print… in a desktop window opens the pages as a PDF in the computer's PDF viewer, which prints them"
status: undecided
applies-to: all
date: 2026-11-15
round: "The three desktop clients: one server, files, printing (branch clients)"
supersedes: []
superseded-by: []
---

# D502 · Proposal: Print… in a desktop window opens the pages as a PDF in the computer's PDF viewer, which prints them

**Proposal: in a desktop window, Print… in the print preview hands the PDF the preview already makes to the shell
(`save_file` with `purpose: print`), which writes it to a folder of its own in the temporary folder and opens it with
the computer's application for PDFs (GNOME's default through `Gtk.FileLauncher`, Preview with `open` on macOS, the
default app through Explorer on Windows); the bar says "The pages are open in your PDF viewer: print them from there."
The browser keeps its own print dialog.**

**Notes.** D158 (2) named printing a shell service and left it unbuilt. In a browser the preview prints the PDF in a
hidden frame; a desktop web view cannot do that (WebKitGTK and WKWebView show no PDF in a frame, and WKWebView in
Neutralino has no `window.print()`), so Print… did nothing there once the fonts were in place (D500). A native print
dialog of each OS fed with the PDF would be one step shorter, but needs a PDF renderer in each shell (Poppler on Linux,
PDFKit on macOS, none built into Windows); the viewer prints what the preview shows, with the printers and settings the
person knows. To be confirmed by the owner.
