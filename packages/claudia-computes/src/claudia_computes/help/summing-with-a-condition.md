---
id: computes.summing-with-a-condition
title: How do I add up only the rows that meet a condition?
apps: computes
language: en
tags: sumif, countif, criteria, condition, total
explains: SUMIF, COUNTIF, SUMIFS
---
`SUMIF` adds up the numbers of a range, but only where another range meets a criterion:
`SUMIF(range to test, criterion, range to add up)`. `COUNTIF` counts instead of adding. A criterion is a value to
match, or text such as `">15"`, `"<>done"` or `"north*"` (the `*` matches any text).

## Example

```
      A            B
1   north         10
2   south         20
3   north         30
```

`=SUMIF(A1:A3, "north", B1:B3)` gives 40: it adds `B1` and `B3`, the rows where `A` is `"north"`.
`=COUNTIF(B1:B3, ">15")` gives 2: `B2` and `B3` are greater than 15.

Need more than one condition at once? `SUMIFS` takes pairs of a range and its criterion, all the same shape as
the range being summed: `=SUMIFS(B1:B3, A1:A3, "north", B1:B3, "<25")` gives 10 — only `B1` is in the north rows
*and* under 25.

## When it does not work

- `#VALUE!`: the ranges do not all have the same shape (same number of rows and columns).
- A criterion in quotes that starts with a comparison (`">15"`) is treated as a comparison, not literal text — to
  match a cell that literally starts with `>`, there is no escape for it today; rephrase the comparison instead.
- Everything compares the cell's own value; `SUMIF`/`COUNTIF` never evaluate the criterion range as a formula.
