---
id: D912
title: "Words are hyphenated at line ends, and a paragraph's lines are chosen together, as TeX does"
status: current
applies-to: all
date: 2026-11-12
round: "Pages, print preview and PDF (branch layouting)"
supersedes: []
superseded-by: []
---

# D912 · Words are hyphenated at line ends, and a paragraph's lines are chosen together, as TeX does

**The layout library chooses the lines of a paragraph all at once, by Knuth and Plass's algorithm (TeX's), and breaks words with a hyphen where the CSS property `hyphens` allows: `none` never; `manual` (the CSS default) only at a soft hyphen (U+00AD) typed into the word; `auto` also where the patterns of the text's language allow (D913, D915).** The rules are fixed, not settings: a word is hyphenated only if it has at least 5 letters, with at least 2 before the hyphen and 3 after; at most 2 lines in a row end in a hyphen; the last line of a paragraph is (as good as) never the end of a hyphenated word. The breaker runs up to four passes: strictly without pattern hyphens (TeX's tolerance 100), with them (200), with 1.5 em of extra stretch per line for a measure too narrow for its words (TeX's emergency stretch), and finally accepting anything, breaking a word too long for a line between its letters. Ragged lines (left, centre, right) are weighed against 3 em of free slack, so they come out even too. Hyphenation shows only on pages (print preview, PDF), not in the flow view, where the browser breaks lines its own way. In composes, Body text and the styles based on it hyphenate (`auto`), Title and headings do not (`manual`); Ctrl+- types a soft hyphen and Ctrl+Shift+- a non-breaking hyphen (U+2011), as in Word and LibreOffice; the style editor's Paragraph section has a Hyphenate box.

**Notes.** `hyphens` is `CSS_VERSION` 4, in the paragraph facet. Every quantity is a whole mpt and the badness is TeX's integer formula, so every engine breaks the same way (D910); `LAYOUT_VERSION` is now `claudia-layout-2`. Measured: on a 250 pt measure of German text in 10 pt Inter no space is stretched to more than twice its width; on a 150 pt measure a 34-letter compound forces the emergency pass. Not done: a person's own hyphenation exceptions, hyphenation at page ends (TeX does not prevent it either), and a different language per paragraph (D915).
