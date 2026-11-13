---
id: D313
title: "The cell styles a workbook starts with: Body text, Header, Input, Result, Note"
status: current
applies-to: computes
date: 2026-11-10
round: "Styles as facets, slots and bundles (styles round)"
supersedes: []
superseded-by: []
---

# D313 · The cell styles a workbook starts with: Body text, Header, Input, Result, Note

**A new workbook gets, beside its object styles, five cell styles named by purpose (D62), written in palette roles (D200), all based on Body text:**

  | Style | For | Look |
  |---|---|---|
  | Body text | every cell that has no other style (the sheet default) | the app font, `@text` |
  | Header | the labels at the top of a table or the start of a row | weight 600, `@accent/14` background, bottom border `@accent` |
  | Input | a number someone is meant to change (an assumption in a model) | `@accent` text on `@highlight/14` |
  | Result | a number the model works out and someone reads | weight 600, top border `@structure` |
  | Note | a remark beside the numbers | italic, `@muted` text |

**Notes.** "Input" and "Result" come from the financial-modelling and education use cases: they say what a cell is *for* — which numbers a person may change and which the model works out — the distinction the co-thinking ideas of the product build on. Nothing here is a number format (D75). The exact looks are reviewed in the computes mock-ups of the plan's step 2.1 and may be tuned there without a new decision; the five names and purposes are decided. Confirmed by the owner on 2026-11-10.
