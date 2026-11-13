---
id: D247
title: "The Linux package is one .deb named claudia-office"
status: undecided
applies-to: all
date: 2026-11-10
round: "E5.8 Linux client: three apps, other servers, HTTPS"
supersedes: []
superseded-by: []
---

# D247 · The Linux package is one .deb named claudia-office

**Proposed: one Debian package, `claudia-office`, holds the three applications; it replaces and provides `claudia-composes`.**

**Notes.** The owner asked for one .deb that installs three launchers. The name is a proposal; changing it is a one-line change in `packaging/debian/build-deb.sh` and `.github/workflows/deb.yml`.
