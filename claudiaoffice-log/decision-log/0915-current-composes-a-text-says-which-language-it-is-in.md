---
id: D915
title: "A text says which language it is written in; a new one starts in its creator's"
status: current
applies-to: composes
date: 2026-11-12
round: "Pages, print preview and PDF (branch layouting)"
supersedes: []
superseded-by: []
---

# D915 · A text says which language it is written in; a new one starts in its creator's

**A composes text carries its language as a BCP 47 tag (`de`, `en-GB`), or none: `TextModel.language`, changed in one step for everybody (`SetLanguage`; wire `language`, `set_language`; event `language`).** It is what the text is hyphenated by (D912) and what the PDF says it is in. A new text starts in the language of its creator's interface: the client that made it sets it right away, as the creator's first step. The print preview's bar has a Language choice (the languages the server can hyphenate, and the text's own if it is another; viewers cannot change it), and says so when a text is not hyphenated because it has no language or the server has no patterns for it.

**Notes.** A language per paragraph style (CSS has no property for it; HTML's `lang` attribute is what browsers use) is left for later: one document language covers the common case, and a style override can be added without changing this. Older texts have none and are not hyphenated until someone sets it; their pages look as they did.
