---
id: D480
title: "A formula can give a matrix, and the operators work cell by cell on ranges"
status: current
applies-to: computes
date: 2026-11-14
round: "Excel function coverage (branch excel-functions)"
supersedes: []
superseded-by: []
---

# D480 · A formula can give a matrix, and the operators work cell by cell on ranges

SORT, FILTER, UNIQUE, SEQUENCE, TRANSPOSE, MMULT, LINEST and the like give a `Matrix` (`claudia_computes.spill`): a
rectangular, non-empty grid of values. It spills like the result of `SQL()` and is `#SPILL!` when something is in the
way; a 1×1 matrix is its single value. Handed on as an argument it is a `Range`; where one value is wanted and the
matrix has more than one cell it is `#VALUE!`.

The operators (`+ - * / ^ & = <> < <= > >=`, unary minus, `%`) work cell by cell when an operand is a range or matrix
of more than one cell: a single row or column repeats, a missing position is `#N/A`, an error in a cell is that
cell's error. `=A1:A3*2` therefore spills three cells where it used to be `#VALUE!`; FILTER's condition
(`=FILTER(A1:B9, A1:A9>4)`) needs this.

**Notes.** A blocked `#SPILL!` result now records what it read, so it is calculated again when the blocker is
cleared. The message of an edit refused inside a spill names the formula, not only SQL(). Empty cells in a matrix
result are 0, as in Excel.
