# Claudia

A privacy-first open source office suite: **composes** (text), **computes** (tables), **creates** (presentations). Documents live on a server you choose, are shared live, and an AI that runs where you decide works in the document as one more participant.

This tree holds the shared kernel, the server and the first drafts of all three apps.

```
packages/
  claudia-core/       the kernel: commands, log, undo, regions, checkpoints, redaction, manifest (stdlib only, no I/O)
  claudia-computes/   mini-port of the computes demo: sheets, cells, structure edits (proves the kernel)
  claudia-composes/   text: paragraphs, styles, authorship, the ± n words region, AI suggestions
  claudia-creates/    presentations: slides, text boxes and shapes, the object-set region, a shape library
  claudia-server/     the server: documents, people, live sharing, the AI user, the web app
  claudia-ai/         the language model behind the AI user: OpenVINO model, prompt, answer reading, runner (E7.1)
docs/core-kernel.md   what was built, design points to review, what is left out
```

```
uv sync
uv run pytest
```

## Try the apps

```
./start.sh all          # Windows: start.cmd all
```

starts one server per app and prints how to find each in the browser:

| app | address (with `all`) | start one alone |
| --- | --- | --- |
| computes (tables) | http://127.0.0.1:8765/ | `./start.sh computes` (or `./start.sh`) |
| composes (text) | http://127.0.0.1:8766/ | `./start.sh composes` |
| creates (presentations) | http://127.0.0.1:8767/ | `./start.sh creates` |

Alone, every app uses port 8765 (`--port` changes it). Documents are kept sealed in `demo-docs*`; `./start.sh --help`
lists all options. The first start builds the web app (needs Node.js 22 or newer).

Requires Python 3.14 (`uv` fetches it). Design notes: `docs/core-kernel.md`.
