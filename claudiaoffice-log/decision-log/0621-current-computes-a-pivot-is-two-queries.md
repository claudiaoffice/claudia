---
id: D621
title: "A pivot is two queries: which members there are, then one CASE column for each"
status: current
applies-to: computes
date: 2026-11-15
round: "Pivot tables (branch pivot)"
supersedes: []
superseded-by: []
---

# D621 · A pivot is two queries: which members there are, then one CASE column for each

**SQLite has no `PIVOT` and a query's columns are fixed when it is written, so `compute_pivot` first asks for the members of the column field (`SELECT DISTINCT`, after the filters) and then runs one query with `SUM(CASE WHEN "Quarter" = 'Q1' THEN "Amount" END)` for each member.** Members are written into the text as literals with their quotes doubled, never bound, so the text a person is shown is exactly what runs, and run alone (`SQL(...)`) gives the same rows as the pivot. The total row is a second `SELECT` over the same rows joined with `UNION ALL` (SQLite has no `ROLLUP`); a pivot without a row field is that one row. The total column is the same aggregate without the `CASE`.

**Members are ordered** numbers first, then text without regard to case, then the blank ones last (`ORDER BY "f" IS NULL, "f" COLLATE NOCASE, "f"`); a blank member is shown as `(blank)`.

**This version takes** at most one row field and one column field (the definition holds tuples, so the limit can go without changing anything stored), any number of value fields, sum, count, average, min and max, filters that keep a list of members, and a total row and a total column that can each be left out. Two value fields with one title are refused. A pivot may have at most 1,000 columns of numbers; SQLite's own limit is 2,000.

**Notes.** *Open:* SQL groups case-sensitively (`north` and `North` are two rows) and Excel does not; this is to be settled when an Excel file with such data is read (D625). Sum, average, min and max do what SQLite does with text in a column (a sum treats it as 0, as Excel's pivot sum does). Standard deviation, variance and median need aggregates registered with the engine (D605 notes that this is possible). Dates are serial numbers (D370): grouping by month, quarter or year needs a conversion in the generator and is not in this step. Each of the two queries copies the source into a private database, so a pivot over a very large table pays for it twice; a cache per source revision comes when it is felt.
