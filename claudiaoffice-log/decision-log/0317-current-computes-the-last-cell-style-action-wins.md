---
id: D317
title: "Cell styles: the last action wins, and the layers stay"
status: current
applies-to: computes
date: 2026-11-11
round: "Styles as facets, slots and bundles (styles round)"
supersedes: []
superseded-by: []
---

# D317 · Cell styles: the last action wins, and the layers stay

**Styling cells always gives every selected cell the new style, whatever was there before: the last action wins.** Styling column B after some of its cells were styled gives all of column B the new style; styling a cell after its column gives that cell its own. One action is one undo step.

**The layers of D307 stay**, for what they are good at: a style applied to a whole column, row or sheet is kept as one range of that shape, so the column's empty cells and the cells typed into it later take its style, and "Clear cell style" takes the selected cells' own style away so that the row's, column's or sheet's style shows through again (or Body text).

**How.** One action becomes a few replacements in one step (`CellStyles.plan`, `SetCellStyle.applying`): a range writes the range layer; whole rows write the row layer and clear the range layer inside them; whole columns write the column layer and clear the range layer inside them, except where a whole row's style crosses them, which a piece of the range layer overrides (a row is more specific than a column); the whole sheet writes the sheet layer and clears the others.

**Notes.** Refines D307, whose fixed precedence (range, row, column, sheet) stays the lookup order but no longer decides what a person sees after an action: with precedence alone, styling column B after B2:B5 left B2:B5 as they were, which looks as if the click did not work on them, and is not what spreadsheets have taught people. Asked by the owner on 2026-11-11 ("the last action wins").
