# The AI in composes (E7.10, D680, D681)

Branch `composes-ai`, 2026-11-16, on top of main `b66fae0`. Composes had only the scripted stand-in (`standin_text.TextEngine`): `apps._LENSES`
had no entry for it, so `model_assistant_for` returned `None` and a server started with `--ai` still answered `@ai` in
a text with the stand-in. D640 (merged just before, 2026-11-15) had already opened composes' writes to the AI through
its allow-list (`replace_text`, `set_style`, `suggest`) and taught the stand-in to act; this work adds the model.

## What was built

| Piece | Where | What it does |
|---|---|---|
| The lens | `packages/claudia-server/src/claudia_server/document_lens.py` | `DocumentLens` (the text's counterpart of `WorkbookLens` and `SlideLens`) and `TextRecorder` |
| Methods by words | `packages/claudia-server/src/claudia_server/composes_words.py` | `paragraphs`, `outline`, `replace_words`, `add_paragraphs`, `suggest_words` |
| Wiring | `packages/claudia-server/src/claudia_server/apps.py` | the composes lens, the allow-list, `NOT_FOR_A_MODEL` |
| Who asks | `lens.py`, `model_engine.py` | `Lens.orient(..., asker=, writes=)` |

**The loop is unchanged.** `ModelEngine` knows nothing about texts; it asks the lens where to start, sends read results
through `show` and wraps every write in `recorder`. That is why a text needed only a lens and model-friendly methods.

**Orientation.** How paragraphs (`b1`, `b2`, …) and words are named; the paragraph styles a paragraph can take (the ones
`check_style` accepts); up to 30 headings; the first 12 paragraphs; the asker's paragraph with two on either side when
it is further down; how many suggestions are open. Every piece of the document is fenced as data. The example request
is the one of the asker's mode: `replace_words` in *act*, `suggest_words` in *suggest*, none when she may change nothing.

**Reports.** After a write the model gets the touched paragraphs as they are now, in the order of the text, the ones
that were joined away, and the suggestions the request opened. The recorder listens to `TextChanged`, `BlockSplit`,
`BlocksJoined`, `StyleChanged`, `ItemChanged` and `SuggestionsChanged`.

**Why new methods (D681).** A model cannot count characters; `replace_text` and `suggest` take offsets. The new methods
quote words. A misquote fails with "the words … are not in paragraph b1; read it again and quote it exactly", and the
model can call `paragraphs` with `containing` to find them. `replace_words` goes through `edit_plan` like
`replace_text`, so a line break makes new paragraphs, authorship runs of untouched words stay, and it is one undo step.

**Rights.** Allow-list `MODEL_METHODS["composes"]` = D640's `suggest`, `replace_text`, `set_style`, plus
`suggest_words`, `replace_words`, `add_paragraphs`; `SUGGEST_METHODS["composes"]` = `suggest`, `suggest_words`.
`NOT_FOR_A_MODEL["composes"]` = `suggest`, `replace_text`: they stay allowed for the stand-in, which knows its offsets,
but a model is never told about them. The allow-list at dispatch decides everything (SEC-10, D261).

## Client side

The GTK and Neutralino clients show the web app, and D640 had already removed the panel's note that the AI only
suggests in a text, so no client changed. No menu entries or shortcuts were added. The help topic
`composes.asking-ai-to-review` (English and German) got a section on asking a language model.

## Not built

- What the asker has selected, as context (a wire change; E7.5).
- Lists, floating objects, the page, style definitions and names for the AI.
- One answer as one undo unit, "ai, on behalf of X" (E7.7).
- A smoke test with a real model (`claudia_ai check`); the tests play the model with `FakeModel`.
