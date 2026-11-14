---
id: D437
title: "Documents, settings and certificates of the three-server layout are not carried over"
status: current
applies-to: all
date: 2026-11-14
round: "One server, app modules (branch one-server)"
supersedes: []
superseded-by: []
---

# D437 · Documents, settings and certificates of the three-server layout are not carried over

**The one-server layout starts empty: `./start.sh` keeps documents in `.claudia/documents/<app>/` and state in
`.claudia/state/`; the desktop apps in one suite folder each. The folders of the old layout (`.claudia/<app>/`, the
per-app folders of the desktop apps) are ignored, never read and never deleted; `./start.sh` says once that they can
be removed.**

**Notes.** Owner, 2026-11-14: there is no release and no live system yet, so documents, users, server settings and
certificates can all be thrown away and the suite as a system can restart. No document folders are tracked in the
repository (`.claudia/` and `demo-docs*` are ignored), so there was nothing to delete there.
