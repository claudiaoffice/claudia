---
id: D904
title: "The page a text is printed on is part of the document: paper, orientation, margins and page numbers"
status: current
applies-to: composes
date: 2026-11-12
round: "Pages, print preview and PDF (branch layouting)"
supersedes: []
superseded-by: []
---

# D904 · The page a text is printed on is part of the document: paper, orientation, margins and page numbers

**A composes text carries its page setup: a paper (a preset — A3, A4, A5, A6, B5, Letter, Legal, Tabloid, Executive — or a custom size from 25 to 1200 mm a side), an orientation, four margins and whether pages are numbered.** Every length is a whole number of mpt, the layout library's unit, so the stored value is the one the layout uses; width is the short side, orientation says how the paper lies. Changing it is one step for everybody (`SetPageSetup`, with its exact inverse; wire methods `page` and `set_page`; event `page`), so every preview and every PDF of a document use the same page. A new text gets A4 portrait, 2.5 cm margins, no page numbers; an older text without a setup gets the same.

**Notes.** The first step of E9.14 (named page styles): one page per document, no sections, no first-page or left/right pages, and of headers and footers only a page number (`n / N`, centred in the bottom margin). Chosen over keeping the paper only in the preview because the owner wants every rendering of a document to be the same (D901). The margins are checked to leave at least 10 mm for the text either way the paper lies.

*2026-11-13:* `PageSetup` moved to `claudia_core` and is shared with creates, which adds the paper `slide` (**D917**).
