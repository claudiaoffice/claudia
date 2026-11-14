---
id: D377
title: "Dates are Excel's day count, its 29 February 1900 included; date and money functions compute as Excel's do; a reference only asked where it is is no dependency"
status: current
applies-to: computes
date: 2026-11-13
round: "Real-world documents: date and money functions (branch real-world-docs)"
supersedes: []
superseded-by: []
---

# D377 · Dates are Excel's day count; date and money functions compute as Excel's; shape-only references are no dependency

**A date is a whole number of days and a time of day the fraction of one, counted as Excel counts them in its 1900
system: day 1 is 1 January 1900, and day 60 is a 29 February 1900 that never was (Lotus 1-2-3's mistake, kept by
Excel so that old files keep their dates).** From day 61 (1 March 1900) on the count is the calendar's. Day 0 shows as
0 January 1900; the last day is 31 December 9999 (2,958,465). This settles "date system" in D12's open list: a date
in an xlsx or ods file means the same day here, and the same number. Text is never read as a date (E6.4).

**The date functions** — `DATE`, `YEAR`, `MONTH`, `DAY`, `EDATE`, `EOMONTH`, `DAYS`, `WEEKDAY`, `DATEDIF` — follow
Excel, including its carrying over (`DATE(2026,14,1)` is February 2027, day 0 is the last day of the month before) and
its errors (`#NUM!` outside 1900–9999). **The money functions** — `PMT`, `PV`, `FV`, `NPV`, `IRR` — use Excel's signs
(money paid out is negative) and its `type` (payments at the start or the end of a period). `NPV` and `IRR` read their
cash flows row by row in the order the cells stand, numbers only. `IRR` uses Newton's method from the guess and halves
an interval where the value changes sign when that does not settle; `#NUM!` when there is no rate.

**A reference passed straight to `ROW`, `COLUMN`, `ROWS` or `COLUMNS` is not a cell the formula reads**, so it is no
dependency: `=COLUMNS($B$3:B3)` in B3 counts columns and is not circular, as in Excel. A reference that also appears
anywhere else in the formula is read as before.

**Notes.** Found on the real planning workbook of D370: 6,857 of its formulas came in as values for want of these
functions (`YEAR` alone 5,397), and once they were live, 6,800 of them turned `#CIRC!` on the `COLUMNS($B$3:B3)`
pattern. With both, 52,685 formulas are live and 52,672 compute exactly what Excel stored. Of the rest, one is D372's
decimal comma, ten are a real circle in the file that Excel, without iteration, shows as 0 and claudia as `#CIRC!`,
and two are `IRR` over a range holding `#REF!`, where Excel answers `#VALUE!` and claudia passes the `#REF!` on. `TEXT`
waits for named number formats (E6.14); `CONVERT`, `FORMULATEXT` and `CELL` are not built.
