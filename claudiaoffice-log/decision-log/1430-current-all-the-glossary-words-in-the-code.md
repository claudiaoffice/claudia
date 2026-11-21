---
id: D1430
title: "The names the code gives the glossary's notions where a glossary word was already taken: holder, object layer, ChartTab, WhatIfProposal, BranchInfo, claudia-document-file"
status: current
applies-to: all
date: 2026-11-21
round: "Architecture improvements and the glossary words in the code (branch architecture-improvements)"
supersedes: []
superseded-by: []
---

# D1430 · The names the code gives the glossary's notions

E1.18 renames the code to the words of `glossary.md`. Most target words were already used in the code for something
else. The owner decided, on 2026-11-21:

| Glossary notion | Code today | Code after E1.18 | What happens to the name that was in the way |
|---|---|---|---|
| **Holder** (new notion) | `Anchor.container`, `containers()`, "container" of an object | `Anchor.holder`, `holders()` | "container" is free for the glossary's Container |
| **Object layer** (new notion) | `TextContainers.vue`; "the shared object layer" in `objects.py` | `TextObjectLayer.vue`; `objects.py` keeps the word | — |
| **Container** | object kind `rendered`, `RenderedDefinition`, renderings | object kind `container`, `ContainerDefinition` | see Holder |
| (the document file) | package `claudia-container` | package `claudia-document-file` (`claudia_document_file`) | — |
| **Chart** | `DiagramDefinition`, object kind `diagram`, `define_/update_/forget_diagram` | `ChartDefinition`, object kind `chart`, `define_/update_/forget_chart` | computes' `Chart` (a chart tab) becomes `ChartTab`, `add_chart` becomes `add_chart_tab`; computes' `ChartSpec` stays (it is computes' `ChartDefinition`) |
| **Paragraph** | composes `Block` (an alias of `claudia_core.Paragraph` since E10.17), `block`, `block_kind`, `blocks` | `Paragraph`, `paragraph`, `paragraph_kind`, `paragraphs` | none: they were one notion already |
| **Proposal** | composes `Suggestion`, `ProposeSuggestion`, `AcceptSuggestion`, `ResolveSuggestion`; AI mode `suggest` | `Proposal`, `Propose`, `AcceptProposal`, `ResolveProposal`; AI mode `propose` | the what-if's `claudia_core.what_if.Proposal` becomes `WhatIfProposal`: one is shared, the other private, and they stay two mechanisms |
| **Step** | `log.Entry` | `Step` | `history.Step` (one undo unit) becomes `UndoUnit`; the assistant's `Step = Say \| Call` becomes `AiTurn` |
| **Branch** | `document.Line`, `lines()`, `peek_line` | `BranchInfo`, `branches()`, `peek_branch` | `Line` was a read view of `revision.Branch` (its head and whether it is the active one added), as `CheckpointInfo` is of a checkpoint. "Line" for a row or a column stays |
| **ai** | `assistant`, `Account.system` | `ai` | — |

**Remarks stay inside composes' `Proposal`** for now, marked by a replacement of `None`, as `Suggestion` carries them
today. The glossary keeps Remark a notion of its own; splitting it from Proposal in the code changes behaviour, not
only names, and is a backlog item of its own.

**Stored names change outright.** claudia is pre-release, so command kinds, object kinds and wire names are renamed
without upcasters or shims for existing documents (E1.18). Checked-in fixtures, test documents, specs, importers and
exporters are changed with them.
