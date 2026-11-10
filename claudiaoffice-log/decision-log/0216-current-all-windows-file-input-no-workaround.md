---
id: D216
title: "Proposal: `<input type=\"file\">` needs no shell-side workaround on Windows, unlike macOS (D158's `file-dialog.ts`)"
status: current
applies-to: all
date: 2026-11-08
round: "Neutralino on Windows and macOS (twenty-eighth round)"
supersedes: []
superseded-by: []
previous-id: D160
---

# D216 · Proposal: `<input type="file">` needs no shell-side workaround on Windows, unlike macOS (D158's `file-dialog.ts`)

**Proposal: `<input type="file">` needs no shell-side workaround on Windows, unlike macOS (D158's `file-dialog.ts`).** WKWebView (macOS's engine) shows no native Open panel for a file input without a WKUIDelegate method Neutralino's binary does not implement — a real bug found on the owner's own Mac. WebView2 (Windows's engine) is Chromium, and Chromium has handled `<input type="file">` with its own native picker since before Neutralino existed. On this reasoning, `clients/windows/` ships with no `file-dialog.ts` at all — composes' Insert Image dialog is expected to work unmodified.

**Notes.** A hypothesis, not a confirmed result — nobody has clicked that button on a real Windows machine with this client. If it turns out WebView2 needs the same workaround after all, a Windows `file-dialog.ts` can be added the same way macOS's was: the Neutralino surfaces it would call (`os.showOpenDialog`, `filesystem.readBinaryFile`) are identical between the two shells (`notes/e0-3-neutralino-windows-macos.md` §7). Flagged in `clients/windows/README.md`'s "Not verified".

*Renumbered on 2026-11-10 from D160, a number that had been allocated twice by branches written in parallel (see `_rounds.md`, "One file per decision").*

*Written as a proposal; confirmed by the owner on 2026-11-10, since the code already follows it.*
