---
id: D378
title: "A workbook has named number formats in Excel's code; a style may name one; a client shows numbers through it in the reader's way"
status: current
applies-to: computes
date: 2026-11-13
round: "Real-world documents: cell formats and number formats (branch real-world-docs)"
supersedes: []
superseded-by: []
---

# D378 · Named number formats in Excel's code, part of a style, shown the reader's way

**A workbook keeps its number formats in a book of its own, each with an id, a name and a code in Excel's syntax**
(`#,##0.00 "€"`, `0.0%`, `dd.mm.yyyy`, `[h]:mm`). Excel's code is what every spreadsheet reads and writes (an ods
file's number styles say the same things, and are read into and written from it), so it is the one way to write a
format here. A format that came from a file has a provisional name saying what it shows (`MWh`, `€, 2 decimals`,
`percent, 1 decimal`, `short date`) and `to_name` set until somebody names it, like a provisional style (E9.7).

**A style may name a number format (`StyleDef.number_format`)**, inherited like its CSS: a style without one shows
numbers as its parent does. Number formats are not CSS, so they are not a facet; they belong to the words of a cell,
and only the words slot's style decides how its number looks. Body text names none: a number shows as it comes
(*General*). A cell has no format of its own (D306): to show one number differently is to give it another style.

**A client shows a number through the code in the reader's language and region**: the decimal and thousands
separators, the names of months and days, and Excel's built-in format 14 (`m/d/yyyy` in the file) as the reader's
short date. A code's own locale mark (`[$-407]`) and its text stay as written. The Python renderer
(`claudia_computes.numformats`) and the TypeScript one (`web/app/lib/number-format.ts`) are twins checked against
the same cases (`number_format_cases.json`). `TEXT(value, code)` uses the same renderer with English separators —
the locale of a formula's text is still open (D372).

**Notes.** Asked of the owner while patch 3 was planned (2026-11-13): "Named formats (Recommended)". A format code the
renderer does not understand is refused when it is added; one in a file comes in as *General* and is counted as a
`look` loss (`number-format`). Excel's East Asian built-in formats (27–36, 50–81) are such a case.
