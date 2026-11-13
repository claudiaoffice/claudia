---
id: D303
title: "Every style property belongs to exactly one of four facets; the facets are a table in core, and a facet owns its vocabulary, its checks and its mappings"
status: current
applies-to: all
date: 2026-11-10
round: "Styles as facets, slots and bundles (styles round)"
supersedes: []
superseded-by: []
---

# D303 · Every style property belongs to exactly one of four facets; the facets are a table in core, and a facet owns its vocabulary, its checks and its mappings

**Every property a style can set belongs to exactly one *facet*, and the table of facets lives in `claudia_core`.** The facets are:

  | Facet | What it says | Properties today |
  |---|---|---|
  | **Text** | how characters look | `font-family`, `font-size`, `font-weight`, `font-style`, `text-decoration`, `color`, `letter-spacing`, `word-spacing` |
  | **Paragraph** | how a stretch of text is laid out | `text-align`, `line-height`, `margin-*` (indent and wrap later) |
  | **Box** | a rectangle around content | `background-color`, `border-top/right/bottom/left`, `padding-*`, `vertical-align` (D307) |
  | **Outline** | a shape's paint | `fill`, `stroke`, `stroke-width` (D178) |

**A style is technology-agnostic at the level of facets.** What is stored stays one validated property bag in CSS notation (so D73's CSS view, the single allow-list of D75 and the one `StyleDef` shape stay as they are); *which* property names exist, how a value is checked, and how a facet reaches a render or export target is the facet's own business: Text and Paragraph and Box become CSS on the web, Outline becomes SVG presentation attributes, and each has its own mapping to docx, xlsx, ODF and the typesetter. Box and Outline stay two facets because a cell needs a border per side and a shape is not a rectangle.

**Notes.** Until now the allow-list was one flat table (`_CHECKS`) and "what applies to what" was decided in several places (`slide-style.ts` split text from paint, `StyleHost.parts` said `words`/`box`, composes filtered styles by id). One table of facets is the thing those three were each approximating; `parts` becomes "the facets this slot reads" (D304). "CSS" in the first diagram of this round was shorthand for the notation, not a claim that every facet renders as CSS. Refines D73 and D75; narrows nothing in them. Diagram: `notes/mockups/styles-model-facets-slots.svg`. Agreed with the owner on 2026-11-10.
