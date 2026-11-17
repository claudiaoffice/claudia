---
id: D745
title: "The Windows installer ships no AI runtime, and no MSI yet"
status: current
applies-to: all
date: 2026-11-17
round: "The Windows installer (E8.1; branch `win-installer`)"
supersedes: []
superseded-by: []
---

# D745 · The Windows installer ships no AI runtime, and no MSI yet

**Out of the installer for now** (the owner, 2026-11-17): the AI runtime (OpenVINO) and models. A user's own models are the
user's to bring (D13); the installer's size is the three apps, the server and Node. When it comes it is an optional component
that downloads at install time, not part of the file. **MSI** for managed rollouts (public administration, schools) is for
later; the installer's staging (`build.py stage`) is what an MSI build would take.
