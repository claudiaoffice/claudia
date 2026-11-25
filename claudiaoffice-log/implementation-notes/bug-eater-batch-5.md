# Implementation note: bug eater, batch 5

Written 2026-11-25, branch `batch-5` (from `main` at `e3a99e0e`; `backlog` was already in it). The brief is
`notes/bug-eater.md`; the batch comes from the architecture review of 2026-11-25 (candidates 3, "one reader's view",
and 4, "who may send a command"), agreed with the owner in two rounds of questions the same day. One helper did SEC-27
in a worktree of its own; its commit was taken over as it was. One commit per item, its message starting with the IDs.

## What changed, per item

| Item | Change | Test written first (seen red) |
|---|---|---|
| SEC-25 (D2007) | Every kind of change says who may send it (`Command.sender`, `"person"` by default). `apply` decodes with `registry.for_persons()`, which refuses a server-only kind with `ServerOnly` (`forbidden`) at any depth: a `Batch` decodes its changes through the same registry. Server only: `core.Import`, `Setup`, `Checkpoint`, `Redaction`, `Redacted`, `Restore`, `Switch`, and `computes.ApplyCalculated` (found by reviewing the list). `tests/command_senders.json` lists all 91 kinds | `test_server_protocol.py`: an editor's `apply` of each of the seven, alone and in a batch, is refused and the history unchanged (all seven were accepted); `test_server_computes.py` for `ApplyCalculated`; the reviewed list (no file yet) |
| SEC-24 (D2008) | `audience.Reader` (user, role): `holds(part)`, `reads(message)`, `chat(messages)`, `log(document)`. The export with history, the chat log, the redaction's message numbers and the live push of a message ask it | Ann's export holds the public message, her own private one and Ben's to her, not those between Ben and Cleo |
| SEC-26 (D2008) | The office exports of the three apps take the history from `Reader.log`, empty for a role without its key; a viewer's open suggestions are dated by the document's clock at the export (`Document.now()`) | a viewer's odt, docx (tracked changes too), xlsx, ods, pptx and odp say nothing the history holds |
| SEC-22 | Decided by the owner (b): who wrote what is content. Note of 2026-11-25 in D1261 | a guard, passing from the start: a viewer's `paragraphs` carry the runs |
| SEC-27 (D2009, helper) | Insert ▸ Image has "Don't save the path" (unticked, so the path is saved), with "Everyone who can open this document sees it.", only when a desktop shell says where the picked file is: GTK and Neutralino now send `path` with `picked` (additive to the shell contract, D501). Ticked, an empty path goes; `ImageImport.from_data` keeps `""` as none. The per-person mask (`ImageImport.masked`, every `to_data_for`) is gone: one rule, the person's | server (everyone sees the same path; an empty one is nowhere), core, web (`images`, `shell-bridge`, `local-files`), both shells' `picked` |

**The code review** (two reviewers, standards and spec) found: the viewer's export read the wall clock (now the
document's clock, so the test checks the exact date), `for_persons()` shared the registry's dictionaries, a docstring
copied onto the wrong class, `chat_log` converted every message before slicing, no test for a viewer's Word tracked
changes, and `ApplyCalculated` listed as a person's change. All fixed. Not changed: `Reader.holds` forwards to
`may_read`, which the method table and `welcome` still call directly for role × part (D1261's table stays where it is).

**Versions:** additions under *Unreleased* in the changelogs of claudia-core, -server, -computes, -composes, -creates,
the Linux and the Neutralino clients; the API snapshots regenerated. Versions are raised at release.

**Owner's agreed deviations from the process:** no Gherkin scenario, no E2E test and no mockup for this batch
(2026-11-25: "we don't need a E2E test for this", "I don't need a mock for this small change").

## Assumptions

- `apply` stays the protocol's general way to edit; only the eight kinds are refused. A person's raw change of any other
  kind still skips its method's own checks, as before (see SEC-28 below for the one that matters most).
- The assistant (`Account.assistant()`, the editor "ai") reads the chat as any editor does: public messages and those
  to or from "ai".
- A kept original's own metadata and tracked changes (when an imported file was kept and is patched) are the original
  file's, not Claudia's history, and stay as they were; the owner is asked below.
- SEC-27: ticked sends `""`; with no path known the dialog sends `null`. The tick stays when another file is picked in
  the same dialog; the dialog is new each time it opens, so the tick is back to "save" every time.

## Found in this batch (proposed, not logged)

| ID | Size | What | How known |
|---|---|---|---|
| SEC-28 | 2 | A person's raw `core.DefineAsset` / `UpdateAsset` skips what `add_image` does to a picture: an SVG is sanitised there, but not when an asset is read from its data (`ImageAsset.from_data`). Claudia shows pictures only through `<img>`, where an SVG's scripts never run, but an export or a downloaded picture would carry it to other programs | read |
| CODE-108 | 3 | Both shells cut a path longer than 4096 characters without a word; such a path would be saved wrong | read (helper) |
| PROC-67 | 3 | `uv run pytest clients/linux/tests` cannot load `test_contract.py`: `jsonschema` is not in the uv environment (the Linux README says to use the system python3) | measured (helper) |

## Say what could not be run

- The GTK tests that need a display (`gi` does not import here); the GTK file and contract tests ran without one.
- A real macOS or Windows shell picking a picture: the path's way through them is checked by their unit tests only.
- A screen reader on the new box (its hint is linked with `aria-describedby`).
- Firefox: CI's job.
