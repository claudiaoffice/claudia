---
id: D318
title: "A cell aligns by what it holds, unless its own style sets an alignment"
status: current
applies-to: computes
date: 2026-11-11
round: "Styles as facets, slots and bundles (styles round)"
supersedes: []
superseded-by: []
---

# D318 · A cell aligns by what it holds, unless its own style sets an alignment

**A cell whose style sets no alignment aligns by its content, as every spreadsheet does: numbers right, text left, TRUE/FALSE and errors centred.** Only an alignment set by the cell's style itself, or by one of its parents short of Body text, overrides that. Body text's own `text-align: left` is a paragraph's alignment and does not reach cells.

**In the editor** a cell's Paragraph section has **Auto** beside left, centre, right and justify. Auto is pressed when the style sets no alignment of its own; choosing it takes the style's alignment away (`unset`), so it follows its content again.

**Why.** Every cell has a style (Body text where no range says otherwise, D313), and Body text is based on nothing and says `left`. Read literally, every number in every workbook would be left-aligned the moment cells take styles — a change nobody asked for and that no spreadsheet makes. The alternative, taking `text-align` out of Body text, would change how a text box on a sheet aligns, and would make computes' Body text differ from composes' and creates'.

**Notes.** Found while building plan step 2.6 (`claudia-web`'s `alignOf` in `lib/cell-styles.ts`). A style built for cells that wants numbers centred says so itself (`text-align: center`) and wins over the content. Decided by the implementing agent on 2026-11-11 for the owner's review.
