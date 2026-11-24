Recipes for this app. Adapt the examples to what was asked; do not copy their values.

## Write values and formulas
Uses: set_cells
Each cell is {"row", "col", "input"}: "input" is what a person would type. A number is "42", text is words, a formula starts with "=" and names cells by their address (A1 is row 0, column 0). Several cells go in one request. To check a function you are not sure of, look it up first (functions, function_help).
```commands
[{"method": "set_cells", "params": {"sheet": "s1", "cells": [{"row": 0, "col": 0, "input": "Total"}, {"row": 0, "col": 1, "input": "=SUM(B2:B9)"}]}}]
```

## Add a sheet
Uses: add_sheet
The name must be new and not empty. The answer holds the id of the new sheet: use that id in the requests that follow.
```commands
[{"method": "add_sheet", "params": {"name": "Summary"}}]
```

## Find and replace
Uses: search_replace
`query.text` is what is found, `query.replace` a list of pieces, each {"text": ...} (here one). `kinds` says what is searched: "text" (what was typed), "formulas". `scope` is {} for everything or {"sheet": "s1"}. Only text and formulas are replaced, never the values a formula computes.
```commands
[{"method": "search_replace", "params": {"query": {"mode": "text", "text": "EUR", "replace": [{"text": "USD"}]}, "kinds": ["text"], "scope": {"sheet": "s1"}, "leave": []}}]
```
