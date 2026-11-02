# Claudia

A privacy-first open source office suite: **composes** (text), **computes** (tables), **creates** (presentations). Documents live on a server you choose, are shared live, and an AI that runs where you decide works in the document as one more participant.

This tree is the first draft of Epic 1, the shared kernel.

```
packages/
  claudia-core/       the kernel: commands, log, undo, regions, checkpoints, redaction, manifest (stdlib only, no I/O)
  claudia-computes/   mini-port of the computes demo: sheets, cells, structure edits (proves the kernel)
  claudia-composes/   stub: text with a ± n words region
  claudia-creates/    stub: slides with an object-set region
  claudia-ai/         the language model behind the AI user: OpenVINO model, prompt, answer reading, runner (E7.1)
docs/core-kernel.md   what was built, design points to review, what is left out
```

```
uv sync
uv run pytest
```

Requires Python 3.14 (`uv` fetches it). Design notes: `docs/core-kernel.md`.
