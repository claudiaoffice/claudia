---
id: D236
title: "Branching what-ifs and scrubbing back in time: revision ids allow branches, but there is no API for free what-if branches, only the restore fork"
status: undecided
applies-to: all
date: 2026-11-10
round: "Open design questions"
supersedes: []
superseded-by: []
---

# D236 · Branching what-ifs and scrubbing back in time: revision ids allow branches, but there is no API for free what-if branches, only the restore fork

Branching what-ifs and scrubbing back in time: revision ids allow branches, but there is no API for free what-if branches, only the restore fork.

*Carried over on 2026-11-10 from the decision log's "Open design questions" section, which had no numbers. Nothing here is decided yet.*

**Checked against the code, 2026-11-17 (`main` at `6814bac`).** The code has a what-if primitive now: `Document.scratch(at=None)` runs commands on a private copy (`claudia_core/document.py`, D263's spike), and the history can be shown at any step (`peek_revision`, E5.19). There is still no API for free what-if branches, so the question stays open.
