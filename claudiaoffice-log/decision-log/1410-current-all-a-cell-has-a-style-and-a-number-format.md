---
id: D1410
title: "A cell has a style and a number format, each its own: the style says what the cell is for and how it looks, the number format how its value reads"
status: current
applies-to: all
date: 2026-11-21
round: "Glossary session: domain notions (glossary.md)"
supersedes: []
superseded-by: []
---

# D1410 · A cell has a style and a number format, each its own

**A cell has a style and a number format, and neither decides the other.** The style says what the cell is for
(input, a quote, an explanatory note) and so how it looks: colour, border, font. The number format says how its value
reads: a percentage, an amount in euros, a date, a number of decimals, a text format. A style names no number format.
Two cells of one style may show their values differently, and two cells of one number format may serve different
purposes.

**This holds for every cell, wherever there are cells:** the sheets of computes and the tables of all three apps.

**Setting a number format is not direct formatting.** D306 forbids changing a look outside the style ("leave it as
it is, but make it bold"), so that a document keeps a clean style language whose styles each say a purpose. A number
format does not change the look of a purpose; it says what kind of value the cell holds. So a person picks it per
cell (or per selection of cells) without making a new style.

**Import and export:** where a file format ties a number format to a cell style (an xlsx cell style), the number format
is given to the cells that use that style when the file is read, and written back the way the file format needs.

**Notes.** Asked of the owner in the glossary session (2026-11-21), after the code turned out to follow D378 to the
letter, which reads as if a style names the number format ("a cell has no format of its own: to show one number
differently is to give it another style"). The owner: D378 meant what is written here and used the word "format"
loosely; a style "I use when I quote a percentage" makes no sense. What D378 says about the number formats themselves
stays current: a document keeps them named, in Excel's code, and a client shows them in the reader's way. The word is
now **number format** (glossary.md); "format" on its own is not used. Moving the number format from the style to the
cell in the code is E1.16.
