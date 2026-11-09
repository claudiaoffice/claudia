---
id: computes.writing-a-formula
title: How do I write a formula?
apps: computes
language: en
tags: formula, cell, reference, basics
explains: =, SUM, formula bar
---
A formula starts with `=`. Type it into a cell, or into the formula bar above the grid, and press Enter.

A formula can use numbers, text in quotes, the four arithmetic operators (`+ - * /`), references to other cells
(`A1`, `B2`), ranges of cells (`A1:A10`), and functions (`SUM(A1:A10)`). Click a cell instead of typing its
reference: while you are typing a formula, clicking (or arrow-key-selecting) a cell or dragging a range inserts its
reference at the cursor.

## Example

With 10 in `A1` and 20 in `A2`, typing `=A1+A2` into `A3` and pressing Enter puts 30 in `A3`. If `A1` later
changes to 15, `A3` recalculates to 35 on its own — that is the whole point of a formula: it is not the number
itself, only how to get it.

## Finding a function

Start typing a function's name in the formula bar (`=SU`) and its signature and a short example appear right
there, so you do not have to leave the cell to check what it needs; the full list of functions, searchable, is
under the Help panel's "Documentation" tab.

## When it does not work

- `#VALUE!`: an argument is not the kind of value the function wants (text where a number was needed, for example).
- `#REF!`: a reference points outside the sheet, often because a row or column it depended on was deleted.
- `#DIV/0!`: something was divided by zero, including an empty cell used as a divisor.
- A formula that shows as text instead of a result: it does not start with `=` — Claudia only treats a cell's
  content as a formula when it does.
