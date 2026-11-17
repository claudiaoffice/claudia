---
id: D681
title: "A model names paragraphs by id and words by quoting them, never by offsets"
status: current
applies-to: composes
date: 2026-11-16
round: "The AI in composes (E7.10)"
supersedes: []
superseded-by: []
---

# D681 · A model names paragraphs by id and words by quoting them, never by offsets

**Proposal (Claude, not yet confirmed by the owner): a language model never counts characters in a text.** It names a paragraph by its id (`b3`) and words in it by quoting them exactly (`find`), with `occurrence` to pick one of several and an empty `find` for the whole paragraph. The text app gets five methods for that, open to people and scripts too: `paragraphs` (read in windows of at most 50, optionally only the ones containing some words), `outline` (the headings), `replace_words`, `add_paragraphs` (after a paragraph or at the start, with a style) and `suggest_words` (the assistant only). `replace_text` and `suggest`, which take offsets, stay in the allow-list of D640 for the stand-in, which knows its offsets exactly, but are never described to a model (`apps.NOT_FOR_A_MODEL`).

**Notes.** Why: small local models (qwen, deepseek through OpenVINO) cannot count characters in a paragraph reliably, and a wrong offset changes the wrong words silently, whereas a misquote fails with "the words … are not in paragraph b1" and the model reads again. Rejected: a tool that rewrites a whole paragraph only (loses the authorship runs of every untouched word) and diff-based edits (too much for a small model to write correctly). `add_paragraphs` widens D640's *act* list by one method; it writes only words and paragraph styles, which D640 allows, and drafting new paragraphs is what a writer most asks for. A suggestion stays inside its paragraph, because accepting one inserts text into that paragraph; new paragraphs are proposed as a remark. **Known edge:** `add_paragraphs` at the start puts the new text into the first paragraph and moves what was there into a new one, as pressing Enter at the start of a paragraph does, so a name the first paragraph had stays with the new text.

**Checked against the code, 2026-11-17 (`main` at `6814bac`).** Built as proposed: `paragraphs`, `outline`, `replace_words`, `add_paragraphs` and `suggest_words` (`composes_words.py`, `document_lens.py`, allow-list in `apps.py`), tested in `test_server_composes_words.py` and `test_server_composes_ai.py`. The owner made the code the record of what is decided (log audit of 2026-11-17), so the status is current; replace it with a new decision to change it.
