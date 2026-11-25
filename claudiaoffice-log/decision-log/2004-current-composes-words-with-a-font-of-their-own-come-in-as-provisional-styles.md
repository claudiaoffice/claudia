---
id: D2004
title: "Words of a docx or odt with a font of their own come in as provisional styles, as cells do in computes (D379)"
status: current
applies-to: composes
date: 2026-11-25
round: "Bug eater, batch 4 (branch batch-4): CODE-47"
supersedes: []
superseded-by: []
---

# D2004 · Words of a docx or odt with a font of their own come in as provisional styles, as cells do in computes (D379)

**Decided 2026-11-25** by the owner, for CODE-47: direct formatting of words in an imported text comes in the way D379
brings direct formats of cells into computes, as provisional styles named after what they hold, instead of being a
`formatting` loss.

**Not built; postponed** (the owner, 2026-11-25). Batch 4 found that composes has nothing to hold it yet: a paragraph
has exactly one style, its `runs` say only who wrote what, and only paragraph styles exist (D306's marks were never
built). Building it needs styled stretches of words inside a paragraph that split and join on typing like `runs`, a
style kind for words with a command to set it, and the layout, the renderers, the docx and odt readers and writers, copy
and paste and the editor to follow (`implementation-notes/bug-eater-batch-4.md`). A smaller step was offered and not
taken for now: a paragraph whose words all have the same font of their own gets a provisional paragraph style. Until it
is built, the `formatting` loss the import reports is right (CODE-47 stays open).
