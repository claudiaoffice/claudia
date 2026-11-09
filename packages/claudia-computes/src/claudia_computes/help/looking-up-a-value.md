---
id: computes.looking-up-a-value
title: How do I look a value up in a table?
apps: computes
language: en
tags: lookup, table, xlookup, vlookup, match
explains: XLOOKUP, VLOOKUP, MATCH
---
`XLOOKUP` finds a value in one row or column and gives you the matching value from another: `XLOOKUP(what to
find, where to look, where the answer is)`. It replaces the older `VLOOKUP` and does not need the two ranges to
be side by side, or the lookup column to be the first one.

## Example

A small table of training costs, with the category in column A and the actual spend in column C:

```
      A            B          C
1   Category    Budgeted    Actual
2   Travel       12,000       9,450
3   Training      3,000       2,750
```

`=XLOOKUP("Training", A2:A3, C2:C3)` gives 2,750: it looks for `"Training"` in `A2:A3` and gives the value beside
it in `C2:C3`. If nothing matches, `XLOOKUP` gives `#N/A` unless you add a fourth argument to give instead:
`=XLOOKUP("Marketing", A2:A3, C2:C3, "not budgeted")` gives `"not budgeted"`.

`MATCH("Training", A2:A3, 0)` gives the *position* instead of the value — 2, since "Training" is the second cell
of the range — which is what you need when you want the row number itself, or to feed `INDEX`.

## When it does not work

- `#N/A`: the value was not found, and no fourth argument was given to fall back to.
- `#VALUE!`: the two ranges you gave `XLOOKUP` are not the same length, or not a single row or column each.
- Capitalisation and leading or trailing spaces do not matter for text, but an exact number must match exactly.
