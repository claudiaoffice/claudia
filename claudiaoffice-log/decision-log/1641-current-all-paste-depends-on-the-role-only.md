---
id: D1641
title: "Paste and Paste As depend on the role only, not on the clipboard"
status: current
applies-to: all
date: 2026-11-25
round: "Menus that show what fits: the owner's answers on the mock-ups (branch `menus`, 2026-11-25)"
supersedes: []
superseded-by: []
---

# D1641 · Paste and Paste As depend on the role only, not on the clipboard

**Paste and Paste As ▸ Plain text are shown to editors and owners whatever is on the clipboard. There is no "clipboard" reason among the conditions of D1601. Paste As ▸ Plain text pastes only text: chosen when the clipboard holds no text (a picture, say), it pastes nothing and shows the notice "There is no text to paste." That is a check when it is chosen, not a condition of the menu.**

**Notes.** The owner asked whether Paste could show only when the clipboard holds something. What the clients can tell: the Linux shell is told of every change and sees the kinds of content without reading it; the Neutralino shells can ask for the format (text, image or unknown); Chromium has the experimental `clipboardchange` event, which needs an earlier press on the page or a permission; Firefox, the first browser the project tests in, and Safari read the clipboard only behind a "Paste" prompt the person must press. The owner left the clipboard out; a rule that only some clients could follow would also have made them differ.
