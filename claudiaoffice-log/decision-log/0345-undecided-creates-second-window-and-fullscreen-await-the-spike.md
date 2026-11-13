---
id: D345
title: "How the audience window and fullscreen work in each shell is not decided; the spike decides"
status: undecided
applies-to: creates
date: 2026-11-13
round: "Presenter mode in creates (E10.2, branch `presenter`)"
supersedes: []
superseded-by: []
---

# D345 · How the audience window and fullscreen work in each shell is not decided; the spike decides

**Undecided.** The presenter view wants a second window on the audience's screen, and the audience view wants fullscreen. Proposal: the first version shows the audience view in this window with `P` swapping to the presenter view, which needs no second window; the two-window mode comes when the spike shows it works in Firefox, the GTK shell and both Neutralino shells.

**Notes.** The owner asked for the spike (question 1, 2026-11-13). What the code already says: the GTK shell turns `javascript_can_open_windows_automatically` off and loads a new-window request in the same view (`clients/linux/.../webpage.py`), so a `create` handler is needed; the macOS and Windows shell pages frame the web app without `allow="fullscreen"` and the apps' `nativeAllowList` lacks `window.setFullScreen` and `window.create`, so both need entries and a contract message. Results go to `spikes/e10-2-presenter-window/results/`; this decision is then rewritten.

**Result so far (2026-11-13).** Safari 27.2 on macOS, one screen (`results/safari-27.2-macos-web.json`): fullscreen of an element and of the document work and Esc leaves it; `window.open` gives a window that announces itself, hears the opener and receives keys, and BroadcastChannel, `postMessage` and `storage` all answer in about 1 ms; the Window Management API is absent (the person drags the window to the other screen); the Screen Wake Lock is there; F5 combinations never arrive (D344). Not yet run: Firefox, the GTK shell, the two Neutralino shells, and a second screen. **The first version therefore ships the one-window show** (the audience view fills the window or, where the browser allows it, the screen; `P` swaps to the presenter view in the same window, `F` toggles fullscreen) and requests fullscreen and the wake lock on a best-effort basis. The two-window mode, the shell changes (a `create` handler in the GTK shell, `allow="fullscreen"` and the `nativeAllowList` entries in the Neutralino shell pages) and this decision wait for the remaining runs.
