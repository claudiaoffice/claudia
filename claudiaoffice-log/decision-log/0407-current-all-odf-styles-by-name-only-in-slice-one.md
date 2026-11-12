---
id: D407
title: "In the first OpenDocument slice styles are mapped by name only; facet properties come in round two"
status: current
applies-to: all
date: 2026-11-11
round: "OpenDocument import and export: odt first, maximum preservation (branch openoffice)"
supersedes: []
superseded-by: []
---

# D407 · In the first OpenDocument slice styles are mapped by name only; facet properties come in round two

**Title, Heading 1, Heading 2 and Quotations go to and from the styles of the same name (`Title`, `Heading_20_1`, `Heading_20_2`, `Quotations`); body text is `Standard`, and every other style is body text and is named in the losses.** A style based on a known one (LibreOffice's `P1` made by formatting a heading) is the one it is based on; a `text:h` without a known style is a heading by its outline level, and a level beyond 2 is body text with a `heading-level` loss. A file that lacks the style a block is changed to gets a minimal definition added to its `styles.xml`; a new file gets minimal definitions of the five. Properties of style facets (D303) are not read or written yet.

**Notes.** Matches the stance of D306 (no direct formatting) and D314 (no cell styles in xlsx this round): the first slice carries structure, and the styling that the Format menu edits follows once the facets have a mapping to ODF's `style:text-properties` and `style:paragraph-properties`. Character formatting in a file (a bold span) is untouched by an edit of the paragraph, and counted as `formatting` when read.
