---
id: D481
title: "Where Excel's functions have a choice, claudia's choices"
status: current
applies-to: computes
date: 2026-11-14
round: "Excel function coverage (branch excel-functions)"
supersedes: []
superseded-by: []
---

# D481 · Where Excel's functions have a choice, claudia's choices

* **No `#CALC!`**: FILTER with no match gives `#N/A`.
* **Clock**: `TODAY` and `NOW` read `Scope.clock`; they are calculated when their cell is, not by a timer. Backlog: a
  timer or recalculation on open for volatile cells.
* **No hidden rows** in the model yet: SUBTOTAL 101–111 equal 1–11 and AGGREGATE's "hidden rows" options do nothing.
  Cells whose formula contains SUBTOTAL or AGGREGATE are left out of both.
* **Text as a date** only in `DATEVALUE` and `TIMEVALUE` (ISO, `13 Nov 2026`, `Nov 13, 2026`; times `14:30[:15]`,
  `2:30 PM`); D377/E6.4 stands everywhere else.
* **DOLLAR** always uses `$` and English separators; **CHAR/CODE** use Windows-1252; **ROMAN** forms 1–4 follow the
  subtraction-ratio rule; **FREQUENCY** uses the bins sorted; **ATAN2(x, y)** takes x first; the 1900 date system and
  decimal-based rounding stay.
* **Partial**: `CELL` ("width" is `#N/A`), `INFO` (recalc, numfile, origin, system), `HYPERLINK` (shows its text; no
  link behaviour), `AREAS` (always 1: no unions). **Not done**: `GETPIVOTDATA` (there are no pivot tables).
* LET names are plain names bound while the LET is compiled; a LET value cannot use its own name.
