# The `ai` user and the language model — E3.6, E7.1

Two notes merged: the original design of the `ai` participant (2026-11-01) and the port of the model into the repo
(2026-11-02). Moved here 2026-11-05.

> **Read with SEC-10 in `bugtracker.md`.** The restriction on what the model may ask for is enforced in
> `Agent._take_calls`, inside `claudia-ai`, on the model's generated text. `Assistant._call` dispatches whatever
> method name reaches it, and the generic `apply` method has no account check. That is a filter, not an authorisation
> boundary, and the two stories that make it matter are E7.5 (document content into the prompt) and E3.6/D8 (the
> engine on another machine).

## Design of the AI user

- The AI is a normal participant of a document: a `Connection` named **`ai`** with its own session (author "ai", own
  undo history), subject to roles, limits, locks and the log, acting only through **the same protocol requests** that
  other clients use.
- **One AI user per document and session.** It joins when the first person connects, is not counted as a person for
  the connection limit and idle unload.
- **Protected name:** nobody can log in as `ai` (normalised for case, spaces and Unicode); clients get "The name
  'ai' belongs to the AI assistant. Choose another name."
- **Chat is the interface:** `@ai question` is answered as a chat message from `ai` to the asker. Failures are always
  answered in chat ("I could not answer: …"), so the person is never left waiting silently.
- **Threading:** one worker, one question at a time across all documents (FIFO). Only generation runs on the worker
  thread, on a copy of what it needs; all document access stays on the event loop. Timeouts, shutdown and leaving use
  a `stop()` callback checked per token.

## What was taken from the demo and where it went

| Demo (`sheetserver/ai/`) | Repo |
|---|---|
| `engine.py` `Engine`, `OpenVinoEngine`, `EngineError` | `claudia-ai`: `model.py` (`LanguageModel`, `ModelError`), `openvino_model.py` (`OpenVinoModel`). Renamed because the server already has an `Engine`, the planner |
| `agent.py` `Agent`, `Request`, `Turn`, `Call` | `claudia-ai`: `agent.py` (`Agent`, `Request`, `Turn`, `ToolSpec`, `ToolCall`). The agent no longer knows the protocol: the request lists the tools that may be asked for |
| `service.py` `AiService` | `claudia-ai`: `runner.py` `ModelRunner` — one worker thread, FIFO across documents, a timeout counted from the start of generation, cancel and close stopping generation per token |
| `participant.py` `AiParticipant` | server: the existing `Assistant` does joining, typing, steps and failures. New `model_engine.py` `ModelEngine` keeps the per-person memory (6 exchanges) and turns a `Turn` into `Say`/`Call` steps |
| `__main__.py` flags | `claudia_server/cli.py`: `--ai`, `--ai-device`, `--ai-max-tokens`, `--ai-timeout`; the model is loaded before listening |
| `tests/fake_ai.py` | `claudia_ai.testing.FakeModel` plus tests in three packages |

## Changes to existing code

- `Assistant` accepts an `AsyncEngine` (`async plan_async(task)`), awaited, so a slow model never blocks the event
  loop. This was the constraint named in the code map. The synchronous `Engine.plan` is unchanged.
- `Assistant(max_waiting=…)` refuses questions that would wait behind too many (the demo allowed 4 per document).
  Default `None`, so the stand-in is unchanged.
- `apps.model_assistant_for(model_cls, runner)`; `apps.workbook_context(document)` — how rows are counted, an example
  request, and the sheets as `id: name`, at most 50, with whitespace collapsed so a sheet name cannot add lines to the
  prompt.

## Decisions taken while porting

1. **New package `claudia-ai`.** It knows nothing of documents; the server connects it. Moving it into
   `claudia-server` would be mechanical. E7.1 says "separate AI server", which this is not yet.
2. **Default device is GPU** (D13); the demo defaulted to CPU. A machine without a GPU stops at start-up with a
   message suggesting `--ai-device CPU`.
3. **The model may only call `set_cells`, `add_sheet`, `structure`** (`apps.MODEL_METHODS`), described to it from the
   method table. Not `chat`, `apply`, `undo`/`redo`, `save_checkpoint`, `lock` or `add_user`. The demo allowed every
   write method except `chat` and `set_tracking`. *This is the restriction SEC-10 is about: it is applied when the
   model's answer is parsed, not when a call is dispatched.*
4. **Order of steps:** the model's text first, then its requests; with no text, requests then "Done.". The demo made
   the requests first. A failing request stops the rest and the asker is told why.
5. **Only for workbooks**, like the stand-in; `--ai` with another `--model` is a start-up error. There is no
   `MODEL_METHODS` entry for composes at all.

## The provisional convention

The answer is plain text for the person; if the model was asked to change the document it ends with a fenced block:

````
```commands
[{"method": "set_cells", "params": {"sheet": "s1", "cells": [{"row": 0, "col": 0, "input": "1"}]}}]
```
````

Each entry is a request of the server's protocol, from the `ToolSpec` list the request offers. `<think>…</think>` is
stripped, and running out of tokens while thinking is reported. At most 50 requests per answer. Results are not fed
back to the model: there is no observe-act loop.

## Verified / not verified

- **Verified:** 64 tests at the time (the server package went 204 → 225, claudia-ai 35, one of which needs
  `openvino-genai` installed and skips otherwise); end to end over a real WebSocket with a fake model; the event loop
  stays free while the model works; one question at a time across documents; timeout, cancel and close; the names
  `openvino_genai` 2026.4.1 offers (`GenerationConfig`, `StreamingStatus`, `LLMPipeline`,
  `Tokenizer.apply_chat_template`) on Python 3.14; and the real library's error for a corrupt model folder turned into
  a readable message.
- **Not verified: a real model.** Hugging Face and the PyTorch index are blocked in the build sandbox, so no model
  could be downloaded or converted. **The first run on a real machine is the real test**, and it has not happened.

## Left out on purpose

- The demo's `ai` status event and `welcome.ai` ("ai is working on …, n more waiting"); clients show the existing
  typing indicator. **Queue position is part of E7.1's acceptance and is still open.**
- The 30 s linger after the last person leaves; the repo's assistant lives as long as the document is loaded.
- A cursor or focus for the model's edits; the stand-in shows its cursor, the model's requests carry no focus.

## Open (E7.5 and later)

- **Cell contents are not shown to the model**, so there is no prompt injection from cells yet, and little usefulness
  for questions about data. Both change together.
- No observe-act loop, no streaming; the `commands` block convention is still provisional.
- After a restore (D48) the memory of a conversation may hold content from a line that is no longer active; the `ai`
  user must be told and rebuild its context.
- Effective permissions (E7.4) do not exist: the assistant acts with its own account, and nothing intersects the
  asker's rights with the AI's role.
