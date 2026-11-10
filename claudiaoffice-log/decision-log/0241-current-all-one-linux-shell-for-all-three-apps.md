---
id: D241
title: "One Linux shell for all three apps; no app picker"
status: current
applies-to: all
date: 2026-11-10
round: "E5.8 Linux client: three apps, other servers, HTTPS"
supersedes: []
superseded-by: []
---

# D241 · One Linux shell for all three apps; no app picker

**One Linux shell serves composes, computes and creates, and there is no command that asks which app to open.**

**Notes.** `identity.py` is the one table that names the apps; the window, the application, the command line and the packaging take an identity and never name an app. Three start buttons (`claudia-composes`, `claudia-computes`, `claudia-creates`, one desktop entry, icon and AppStream file each) come from one `.deb`. A shell that opened any app would need a picker, which is not wanted: a window is one app. A fourth app is one more identity, manifest and `apps/<app>/` folder. Confirmed by the owner on 2026-11-10.
