---
id: D247
title: "The Linux package is one .deb named claudia-office"
status: current
applies-to: all
date: 2026-11-10
round: "E5.8 Linux client: three apps, other servers, HTTPS"
supersedes: []
superseded-by: []
---

# D247 · The Linux package is one .deb named claudia-office

**Proposed: one Debian package, `claudia-office`, holds the three applications; it replaces and provides `claudia-composes`.**

**Notes.** The owner asked for one .deb that installs three launchers. The name is a proposal; changing it is a one-line change in `packaging/debian/build-deb.sh` and `.github/workflows/deb.yml`.

**Checked against the code, 2026-11-17 (`main` at `6814bac`).** Built as proposed: `packaging/debian/build-deb.sh` makes one package `claudia-office` (`package=claudia-office`), built and tested by `.github/workflows/deb.yml`. The owner made the code the record of what is decided (log audit of 2026-11-17), so the status is current; replace it with a new decision to change it.
