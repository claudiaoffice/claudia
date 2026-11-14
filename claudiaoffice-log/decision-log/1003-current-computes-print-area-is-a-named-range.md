---
id: D1003
title: "The print area is a named range with its own purpose"
status: current
applies-to: computes
date: 2026-11-14
round: "Printing sheets: the computes print preview (E6.19, branch computes-print)"
supersedes: []
superseded-by: []
---

# D1003 · The print area is a named range with its own purpose

**A sheet's print area is a sheet-scoped name (E6.5) with the purpose *print area*, listed in Tools ▸ Names… like any other, and not a hidden setting. Set Print Area and Clear Print Area (cell menu ▸ Print) make and remove it; Contents ▸ Print area prints it.** A sheet has at most one. It maps to Excel's `_xlnm.Print_Area` and to a print range of an OpenDocument sheet, in both directions.

**Notes.** Follows the idea of cell purposes: what a range is for is written down in the workbook where people can see it. The name follows the range when rows or columns are inserted or deleted, as every name does. A print area is one rectangle; Excel's union of several is read as its first rectangle, and the import says so. Chosen by the owner on 2026-11-14.
