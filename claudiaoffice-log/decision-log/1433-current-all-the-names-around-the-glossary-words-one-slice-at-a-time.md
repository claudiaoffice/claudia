---
id: D1433
title: "The names around the glossary words are agreed with the owner slice by slice: container and paragraph as below, the chart slice waits"
status: current
applies-to: all
date: 2026-11-21
round: "Architecture improvements and the glossary words in the code (branch architecture-improvements)"
supersedes: []
superseded-by: []
---

# D1433 · The names around the glossary words, one slice at a time

D1430 names the main identifier for each glossary word. Each rename also touches names around it (wire methods and keys,
events, stored keys, web state, file names), and some of those collide with names already in use. The owner decided, on
2026-11-21:

- **Before each slice of E1.18 the full list of renames beyond D1430 is shown to the owner and agreed.** Nothing beyond
  D1430 is renamed on a rule alone.
- **The chart slice waits** ("needs more consideration"): `DiagramDefinition`, the object kind `diagram`, computes'
  `Chart`/`charts` and their wire names stay as they are for now. The other slices go on without it.

## Holder (done before this rule; for the owner to confirm)

The holder slice came first, before the owner asked to see each list, so these names around D1430's were chosen by the
same rule as the rest and are listed here for confirmation: `ObjectModel.open_holder`, `close_holder`,
`MAX_OBJECTS_PER_HOLDER`; `VisualObject.holder`, `ObjectText.holder`, `Placed.holder`; stored and on the wire, an anchor,
an `objects` region and the `objects` event say `holder`. Web: `holderOf`, `currentHolder`, `showHolder`;
`lib/text-object-layer.ts` beside `TextObjectLayer.vue`; the page's `data-testid` `object-layer` and
`object-layer-behind`.

## Container (agreed)

The thing becomes `container`; the verb stays, because rendering is what the software outside claudia does.

| Before | After |
|---|---|
| object kind `rendered`, asset kind `RENDERING` (`rendering`) | `container`, `CONTAINER` (`container`) |
| `RenderedDefinition`, module `claudia_core.renderings`, `MAX_RENDERING_SOURCE` | `ContainerDefinition`, `claudia_core.containers`, `MAX_CONTAINER_SOURCE` |
| `ObjectModel.renderings`, stored key `renderings`, event `rendering` | `containers`, `containers`, `container` |
| server module `rendered.py`, `add_rendering_methods` | `containers.py`, `add_container_methods` |
| wire `rendering_types`, `renderings`, `add_rendering`, `set_rendering_source`, answer key `rendering` | `container_types`, `containers`, `add_container`, `set_container_source`, `container` |
| web `RenderedFace`/`RenderedEditor.vue`, `lib/rendering.ts`, `state.renderings`, `renderTypes`, `setRenderingSource` | `ContainerFace`/`ContainerEditor.vue`, `lib/containers.ts`, `state.containers`, `containerTypes`, `setContainerSource` |
| a new container's name "Diagram N" | "Container N" |

Kept: the package `claudia-render`, `RenderDesk`, `render_result`, `renderer`, `renderOutcomes`, `RenderType`, the loss
`rendering-pending`. The web's shared `addRendering` is `addContainerAt`, because each app's session already has an
`addContainer` of its own.

## Paragraph (agreed)

| Before | After |
|---|---|
| composes `Block` (alias), `TextModel.blocks`, `block()`, `block_*`, `BlockAnchor` (kind `block`) | `Paragraph` (claudia-core's), `paragraphs`, `paragraph()`, `paragraph_*`, `ParagraphAnchor` (kind `paragraph`) |
| `SplitBlock`, `JoinBlocks`; `BlockSplit`, `BlocksJoined`, `BlockGenerated` | `SplitParagraph`, `JoinParagraphs`; `ParagraphSplit`, `ParagraphsJoined`, `ParagraphGenerated` |
| stored and wire key `block`, state key `blocks`, events `block_fields`, `block_generated`, style target `{block}` | `paragraph`, `paragraphs`, `paragraph_fields`, `paragraph_generated`, `{paragraph}` |
| wire method `blocks` (the clients' read) | `paragraphs` |
| wire method `paragraphs` (the ai's paged reader) | `read_paragraphs` (the owner's choice, to free the name) |
| web `state.blocks`, `lib/blocks.ts`, `data-block`, `PathBlock`, … | `state.paragraphs`, `lib/paragraphs.ts`, `data-paragraph`, `PathParagraph`, … |
| layout `TextBlock`, `TextDocument.blocks` | `TextParagraph`, `TextDocument.paragraphs` |

Kept, because "block" means something else there: the sealed file's blocks, a fenced block, computes' blocks of rows and
cells, the shared block of a menu, CSS (`display: block`, `margin-block`), `scrollIntoView`'s `block`, the layout
library's flow blocks, the filler character █, and the verb. Where a file's paragraph and the text's paragraph meet in
the converters, the file's side is `docx_paragraph` / `odt_paragraph` (python-docx's class: `DocxParagraph`).

The GTK client has no paragraph "block": it hosts the web client, so nothing changed there.
