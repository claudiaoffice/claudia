---
id: D450
title: "What a converter does not write is a loss, found by comparing facets"
status: current
applies-to: all
date: 2026-11-14
round: "Import and export wiring (branch import-export-wiring)"
supersedes: []
superseded-by: []
---

# D450 · What a converter does not write is a loss, found by comparing facets

**Every converter lists the facets of its model that it writes (`ODT_WRITTEN`, `XLSX_WRITTEN`, ...). A facet outside that list that differs between where the export starts and the model is reported as a loss: `claudia_odf_io.unwritten_changes(before, after, written=..., kinds=...)` gives `not-written` with the facet as its detail and how many entries differ, or the code the export already used for that facet (`layout`, `chart`, `object`, `name`, `planned-time`). For an edit-and-reexport the start is the baseline (the model the file was read as), for a new file an empty document.**

**Notes.** Before this, a patch dropped every change it had no place for without a word, and each export list was kept by hand. Now a slice that teaches a converter another facet takes it off the converter's list, and nothing else has to be remembered. The codes are for the interface to put into words (D299, D405); there is no wording of them yet.
