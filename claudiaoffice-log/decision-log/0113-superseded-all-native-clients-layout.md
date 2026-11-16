---
id: D113
title: "Layout of the native clients"
status: superseded
applies-to: all
date: 2026-11-03
round: "Native clients (eighteenth round)"
supersedes: []
superseded-by: [D660]
---

# D113 · Layout of the native clients

**Layout of the native clients:** `clients/<os>/` holds one package per operating system; an app is an entry point, an identity, a menu manifest and its own desktop files under `clients/<os>/apps/<app>/`. The shell contract is shared and lives in `clients/contract/`. The Linux application id of composes is `de.claudiaoffice.composes`.

**Notes.** `clients/contract/` is Claude's addition, because the contract belongs to no single OS.

**Superseded by D660** (2026-11-15): macOS and Windows share one package, `clients/neutralino/`.
