# Redaction: the contract, the plan and the rewritten file (D720–D726, E1.8, E2.6, SEC-05)

2026-11-16, branch `redaction` from `main` at `ef829d5`. The owner agreed to all four proposals for D229 the same day.

## What moved where

```
claudia-core        Document.plan_redaction -> RedactionPlan          (D721, D722, D724)
                    Document.redact(plan | revisions)                  (D229)
                    Command.redacted() / redacted_in(model)            (D720)
                    Import.blanked(model, parts), DocumentModel.blank  (D723)
                    ObjectModel.blank_objects / blank_diagram, blank_body, FILLER
                    ChatRecord.redacted / blanked, Redaction.chat, Redacted.chat
                    DocumentStore.rewrite(log, chat)                   (D725; replaces replace_entries, drop_snapshots)
claudia-composes    TextModel.blank: paragraphs and objects by id
claudia-computes    WorkbookModel.blank: sheets, "s1!A1:B5", chart tabs, objects; blank_diagram takes the titles
claudia-creates     SlideModel.blank: slides (notes and everything on them), objects
claudia-container   rewrite_journal, forget_original                   (D725, D723)
claudia-server      SealedStore.rewrite (keys kept), JournalStore.rewrite, filestore.history_items / chat_items
                    wire: redaction_plan, redact (owners only)         (D726)
```

## How the plan is worked out

1. Each requested step is replaced by its blanked form: `command.redacted_in(type(model))`, which is `redacted()` for
   every command but an import and a diagram, whose content only the app can judge.
2. Every line whose path holds a replaced step is replayed from the empty model. The first step that refuses is
   blanked too and recorded as a dependent; repeat. A refusal *before* any replaced step means the history was broken
   already and is an error, not a reason to blank. A refusal of a step that is already replaced, redacted or meta is
   the last resort: nothing was redacted.
3. The active line is replayed once more for `after`; `changes_now` compares its `serialize()` with the live model.
4. The plan records the heads of all lines and the chat (`basis`); `redact` refuses a plan whose basis is not the
   document's any more.

The cost is one full replay per affected line per dependent found. Redaction is rare and an owner's act, so this was
preferred over tracking which step depends on which.

## The file

`rewrite_journal` shares `_write_blocks` with packing; the only difference is the fold: packing continues the chains
(`_extend`), rewriting starts them empty (`_sealed_chain(..., [], payloads)`). The journal's generation logic is the
same, so a crash between the new file and the new journal leaves an old journal that `read_state` ignores and `begin`
replaces. If the rewrite fails in the server, `SealedStore.rewrite` reopens whatever journal is on disk (as a failed
packing does) and the kernel puts the log and chat back in memory.

## Behaviour that changed

* `Document.redact([rev])` refuses when other steps would have to be blanked with it; ask for a plan instead.
* A redacted picture keeps its id and size and shows one grey pixel (`BLANK_GIF`); a redacted object loses its
  description and the words of its import record. Tests that documented the old gaps were turned around
  (`test_redacting_an_image_object_takes_its_words_and_its_pixels` in computes and creates).
* The old `replace` journal item is still read (journals written before), but never written.
* The `redacted` event carries `chat`; the Redaction record writes `chat` only when there is some.

## Not done

* The screens (E3.13): mock-ups in `notes/redaction-ui.md`, waiting for the owner.
* An image asset of a redacted picture is blanked, not removed: objects still point at its id (D720). Its id is the
  sha256 of the original bytes; a person who has the picture could confirm it was there. Accepted with the shape rule.
* A rendered container's picture is blanked when an import is blanked; a redacted `DefineRendering` step keeps the
  picture of the old source, which is a step of its own (`DefineImage`) and has to be picked too.
