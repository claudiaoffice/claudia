# Implementation notes: skills and persona per app, with CODE-80 to CODE-82 (E7.2)

Branch `e7-2-skills-and-persona`, decisions D1560 to D1579 (reserved in `ranges.md`). The design is
`notes/e7-2-architecture.md`. This file keeps what the code does that the note does not say, the assumptions made while
building, and what could not be run. It grows with each commit of the branch.

## CODE-80: what a remote provider is first sent (D1568), done

- Two ways to start a question, no flag (the code review found the first version, a `remote` flag threaded through five
  signatures, broke `CONTRIBUTING.md` rule 2 and failed open: `model_assistant_for` built an engine without it). Each lens has
  `orient` (the start of the document) and `outline` (counts and ids). `ModelEngine` asks its runner (`Answerer.remote`, from
  `LanguageModel.remote`) and wraps the lens in `lens.OutlineLens` for a remote one; `GatedRunner.remote` passes it on.
- Workbook: the number of sheets and their ids ("... and N more" past 50), then "look". Text: counts of paragraphs, headings,
  tables and open suggestions, and the id of the paragraph the asker is in, without her name. Presentation: the slides with
  their object counts. A style name a person gave is "a word a person wrote", so styles are not listed either: the model asks
  for `styles`. The paragraph orientation no longer says "the start of the text below" in the outline.
- Not changed: what the model *asks to see* is sent in full; the earlier chat goes with the question whoever answered
  (D1498), so a quotation of the local model's earlier answer reaches Claude (the @core scenario holds for a question without
  an earlier chat).
- Assumption: ids (`s1`, `b3`, `o2`) carry no content. They are minted by the document, not typed by a person.
- Cost: one more round for most questions to Claude (the look). The budget (8 rounds) is not touched.

## What could not be run

- The @core scenario of the browser (`specs/server/claude-answers.feature`) runs only through `./run-e2e.sh`; see the
  delivery report for whether it ran on this commit.
- A real key. Whether Claude, now that it is not shown the document, looks first and well, is what the owner's real-key
  test shows. The persona of the next commit says "look before you answer or change".
