---
id: D454
title: "The page and the language of a composes text are written to odt and docx, read back, and patched into a kept file"
status: current
applies-to: composes
date: 2026-11-14
round: "Import and export wiring (branch import-export-wiring)"
supersedes: []
superseded-by: []
---

# D454 · The page and the language of a composes text are written to odt and docx, read back, and patched into a kept file

**`PageSetup` (paper or custom size, orientation, margins, page numbers) and the language of a text are written to a new odt or docx, read from an existing one, and changed in a kept file when the model changed them. `"page"` and `"language"` are written facets of both converters (D450).**

**Notes.**

* *odt.* The page is a `style:page-layout` with a `style:master-page` (a footer with `text:page-number` when pages are numbered); the language is the `fo:language`/`fo:script`/`fo:country` of the default paragraph style, `zxx` or `none` meaning no language. A patch changes the first master page's layout and the default style, and leaves every other style and master page as it is.
* *docx.* The page is the first section (`w:pgSz`, `w:pgMar`, a footer with a `PAGE` field); the language is the `w:lang` of the document defaults, a text with no language getting `zxx`. A file measures in twentieths of a point, so a custom size that is not a whole number of them (the model has 1/50 pt) is written to the nearest one. The package parts that change (the footer, `[Content_Types].xml`, the relationships, `word/styles.xml`) are taken from the regenerated package; the rest stays as it was.
* *Only the first section* of a docx and the first master page of an odt are read and written; a file with several keeps the others as they are, and a page the model cannot hold (a side that is no length, margins that leave no room) is imported as the default page and reported as `page`.
* *The patch of an odt* was called by the server without the document's `info` and `change_times`; it now gets them, so a patched file says who saved it last and when and dates its tracked changes like a new one (D411).
