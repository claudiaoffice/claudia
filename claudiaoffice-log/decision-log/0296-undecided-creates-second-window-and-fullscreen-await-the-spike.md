---
id: D296
title: "How the audience window and fullscreen work in each shell is not decided; the spike decides"
status: undecided
applies-to: creates
date: 2026-11-13
round: "Presenter mode in creates (E10.2, branch `presenter`)"
supersedes: []
superseded-by: []
---

# D296 · How the audience window and fullscreen work in each shell is not decided; the spike decides

**Undecided.** The presenter view wants a second window on the audience's screen, and the audience view wants fullscreen. Proposal: the first version shows the audience view in this window with `P` swapping to the presenter view, which needs no second window; the two-window mode comes when the spike shows it works in Firefox, the GTK shell and both Neutralino shells.

**Notes.** The owner asked for the spike (question 1, 2026-11-13). What the code already says: the GTK shell turns `javascript_can_open_windows_automatically` off and loads a new-window request in the same view (`clients/linux/.../webpage.py`), so a `create` handler is needed; the macOS and Windows shell pages frame the web app without `allow="fullscreen"` and the apps' `nativeAllowList` lacks `window.setFullScreen` and `window.create`, so both need entries and a contract message. Results go to `spikes/e10-2-presenter-window/results/`; this decision is then rewritten.
