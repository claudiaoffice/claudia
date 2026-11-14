---
id: D452
title: "A patched download lists what the patch lost and what it has no place for"
status: current
applies-to: all
date: 2026-11-14
round: "Import and export wiring (branch import-export-wiring)"
supersedes: []
superseded-by: []
---

# D452 · A patched download lists what the patch lost and what it has no place for

**`export_office` on a document imported in that format answers `losses` also when it patched the kept file: what the patch writer itself reported (`removed-...`, `stale-reference`, given to it as a `LossLog`) and the unwritten changes since the import (D450). Before, a patched answer always had an empty list, and the writers' own losses were never delivered.**

**Notes.** A patched file keeps everything the model does not show, so nothing is lost from the file; the list says which of the person's edits did not reach it. An edit that cannot be patched at all still gives a new file with `not-patched` (D441).
