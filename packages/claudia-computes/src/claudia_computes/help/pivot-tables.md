---
id: computes.pivot-tables
title: How do I summarise a table with a pivot table?
apps: computes
language: en
tags: pivot, pivot table, summary, group, total, sum, count, average, report, xlsx, ods
explains: PIVOT, SQL
---
A pivot table adds up a table for you. You say which column to group by down the side (the rows), which to group by
across the top (the columns) and what to add up (the values), and the pivot table gives one number for each pair. It
stays live: when the table changes, the pivot table changes with it, and there is nothing to refresh.

## Example

A table of sales called `Sales`, with the region in column A, the quarter in column B and the amount in column C:

```
      A         B         C
1   Region    Quarter   Amount
2   North      Q1         100
3   North      Q2         150
4   South      Q1          80
5   South      Q2         120
```

Choose **Tools ▸ Pivot Table…** (Ctrl+Alt+V), keep `Sales` as the source and press Create. In the field panel tick
`Region`, `Quarter` and `Amount`, then put `Region` in Rows, `Quarter` in Columns and `Amount` in Values:

```
      A                 B         C         D
1   Sum of Amount    Quarter
2   Region              Q1        Q2       Total
3   North               100       150       250
4   South                80       120       200
5   Total               180       270       450
```

The first cell holds `=PIVOT("SalesPivot")`, which fills the cells around it. You cannot type over them: change the
pivot table in its panel, or change the source.

## What you can change

- **Where a field goes.** Drag its chip to another box, or open its ▾ menu and choose *Move to …*, which works from
  the keyboard too. A pivot table has one row field and one column field; putting a second one in a full box sends
  the first back to the list.
- **How a value is added up.** Open **Tools ▸ Value Field Settings…** (Ctrl+Shift+Alt+U) to choose sum, count,
  average, minimum or maximum, and to rename the value.
- **Filters.** A field in Filters keeps only the members you choose (its ▾ menu, *Choose members…*).
- **Totals.** The *Total row* and *Total column* switches in the panel turn each on or off.
- **The query.** **Show Pivot Table as SQL…** shows the query the pivot table runs. *Convert to SQL query…* turns it
  into an ordinary `SQL()` result with the same numbers; that is one step you can undo.
- **Removing it.** **Delete Pivot Table…** removes the pivot table and the cells it filled.

## In other programs

A pivot table is saved in `.xlsx` and `.ods` files as a pivot table, with its numbers in the cells, so Excel and
LibreOffice open it as one. Excel makes it again when it opens the file. A pivot table in a file you open comes in as
a live pivot table when Claudia gets the very same numbers from the same source; if not, the cells stay plain cells and
the import report lists the pivot table as not read. Claudia has no pivot table yet for grouping dates, "show values
as", calculated fields, slicers, pivot charts or a source outside the workbook: those stay in the file as they are,
but are not live here.

## When it does not work

- The table is empty: put a field into Values, the panel says so.
- `#SQL!` or another error in the first cell: the panel says which, in the line under its boxes, for example that a
  field is no longer in the source.
- "Its cell was written over, so it shows nothing": something replaced the first cell. Delete the pivot table and
  make it again.
- "There is no table called … (any more)": the source was deleted. Choose another with *Change…* under Source.
