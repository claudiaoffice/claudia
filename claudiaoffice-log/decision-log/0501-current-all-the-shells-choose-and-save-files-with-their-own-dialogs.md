---
id: D501
title: "The desktop shells choose and save the page's files with their own dialogs; an export asks where and says where it went"
status: current
applies-to: all
date: 2026-11-15
round: "The three desktop clients: one server, files, printing (branch clients)"
supersedes: [D216]
superseded-by: []
---

# D501 · The desktop shells choose and save the page's files with their own dialogs; an export asks where and says where it went

**A shell that offers the capability `files` (all three do) shows the computer's own Open and Save dialogs for the page
(contract v1, additive: `pick_file`, `save_file`, `file_chunk`, `file_done`, `file_result`). The page uses them whenever
the shell offers them: Open a File… on the front page and in File ▸ Open, Insert ▸ Image in composes, creates and
computes, and every file the page saves (File ▸ Export…, File ▸ Download, Download PDF). A Save dialog always asks
where, suggesting the document's name and starting in the person's Documents folder, then in the folder last used;
the dialog that saved says where the file went ("Saved as …"); a cancelled dialog leaves it open. A file travels in
pieces of 36 KiB (48 KiB of base64), so no message is over the contract's 64 KiB; files of more than 100 MB are refused.
In a browser tab nothing changes: the file input's dialog and the browser's downloads.**

**Notes.** Owner, 2026-11-15: an export in a desktop window went somewhere without a word and could not be put
anywhere else; the web app's download is "perfect" in a browser. And on macOS "Open a File…" did nothing: WKWebView in
Neutralino shows no panel for `<input type="file">` (found 2026-11-07, `notes/e5-11-macos-client.md`), and no web view
opens a file dialog from a native menu item, which is no click in the page. Where the dialogs come from: Linux, GTK's
`Gtk.FileDialog`; macOS and Windows, the native core (Node), because the page in the frame cannot reach Neutralino —
on macOS AppKit's NSOpenPanel/NSSavePanel through `osascript` (JavaScript for Automation) after making that process an
accessory application and activating it, so the panel comes up in front (Neutralino's own `os.showOpenDialog` runs
AppleScript's `choose file` in a process nothing brings forward, the leading theory of 2026-11-07), with AppleScript's
dialog as the fallback; on Windows the common dialogs of Windows Forms through PowerShell, owned by a top-most form so
they open in front of the window. Supersedes D216 (no workaround for Windows): Windows has the same menu-item problem,
and the same Save dialog is wanted there. **Not verified** on a real Mac or Windows machine.
