---
id: D218
title: "A test-document library (`test-documents/`), a `catalogue.json` deciding which of its files actually get tested, and a new package `claudia-test-documents`…"
status: current
applies-to: all
date: 2026-11-08
round: "Real import, edit and re-export: docx, pptx, xlsx, and the test-document library"
supersedes: []
superseded-by: []
previous-id: D178
---

# D218 · A test-document library (`test-documents/`), a `catalogue.json` deciding which of its files actually get tested, and a new package `claudia-test-documents`…

**A test-document library (`test-documents/`), a `catalogue.json` deciding which of its files actually get tested, and a new package `claudia-test-documents` running it in three tiers instead of comparing whole files byte-for-byte: Tier 1 (`import_checks`/`after_checks`) asserts facts about claudia's own model, not the file; Tier 2 (`preserve_parts`/`preserve_elements`/`export_checks`) targets exactly the bytes that should or should not have moved — a whole package part byte-identical, one element's own serialized XML byte-identical, or the raw re-exported bytes for a feature the model layer cannot see back out again (a tracked change); Tier 3 (`visual`, opt-in, headless LibreOffice plus a Pillow perceptual diff) is a backstop for a property with no structural oracle at all, not used by any case yet.** `scripts/run_test_documents.py` runs some or all of it (`--format`/`--feature`/`--id`/`--tag`, `--visual`, `--report`) and records a `last_run` block per entry it covers, in the same file a person hand-edits the rest of — two writers of one file, never the same fields. Four docx cases ship with it (heading styles; a tracked-change suggestion; a table and an image, each "beyond claudia" — no model for either, checked by Tier 2 alone), generated deterministically by `test-documents/_build_fixtures.py` rather than hand-crafted, and also run as a normal (Tiers 1-2 only, no write-back) part of the `pytest` gate (`tests/test_test_documents_catalogue.py`).

**Notes.** Follows directly from D217: now that a real import/edit/export path exists for one format, this is the test-library design the owner asked to revisit once it did. The three tiers answer the owner's own question of how to check correctness once byte-for-byte comparison is ruled out (it is *replaced* by narrower, exact byte comparisons where that is actually the right check, not abandoned for something fuzzier) and how to do visual comparison without claudia having a PDF/print export yet (LibreOffice renders both files directly; claudia's own export pipeline is not involved in the rendering step at all). A checked-in binary fixture is a deliberate departure from this repo's usual every-format-test-builds-its-document-in-Python convention — the whole point of a *library* was real, openable files, not just assertions — so the generator that produced them ships alongside, kept reviewable and regenerable rather than the binaries being treated as opaque.

*Renumbered on 2026-11-10 from D178, a number that had been allocated twice by branches written in parallel (see `_rounds.md`, "One file per decision").*
