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

## Run with Docker

One image holds the server of all three apps and the web app. As with `./start.sh`, a container serves one app, chosen
with `CLAUDIA_APP` (`computes`, the default, `composes` or `creates`).

```
docker build -t claudia-server .      # needs Docker 23 or newer (BuildKit)
```

Builds of `main` are also published by CI as `ghcr.io/claudiaoffice/claudia-server`, so `docker pull` can replace the build.

```
docker run -d --name claudia-computes -p 8765:8765 -v claudia-computes:/data claudia-server
docker run -d --name claudia-composes -p 8766:8765 -v claudia-composes:/data -e CLAUDIA_APP=composes claudia-server
docker run -d --name claudia-creates  -p 8767:8765 -v claudia-creates:/data  -e CLAUDIA_APP=creates  claudia-server
```

These are the ports of `./start.sh all`: open https://localhost:8765/ (computes), :8766 (composes) or :8767 (creates).
The server makes its own certificate on first start, so the browser warns once.

* **Data.** `/data` holds the documents (`documents/`, each one sealed by its people's passwords) and the server's
  certificate (`state/`). Use one volume per app; the documents survive `docker rm` as long as the volume does. A
  folder mounted instead of a volume must be writable by user id 10001 (`chown 10001:10001 DIR`).
* **Options.** Everything after the image name goes to the server, and `--help` lists it all: `--tls-name
  claudia.example.org` (the name people type), `--no-tls` (behind a TLS proxy), `--tls-cert` and `--tls-key` (your own
  certificate, mounted into the container), `--no-create`, `--no-list`, `--shapes DIR` (creates).
* **Health.** The image checks `/api/health` itself; `docker ps` shows `healthy` once the server is up.
* **AI model.** The image has no language model runtime by default. For `--ai` (only computes uses it so far) build
  with `--build-arg WITH_OPENVINO=true`, which makes the image about 270 MB larger, and mount a model folder. A
  container has no GPU unless you pass one in, so name the device:

  ```
  docker build --build-arg WITH_OPENVINO=true -t claudia-server:ai .
  docker run -d -p 8765:8765 -v claudia-computes:/data -v ~/models:/models:ro claudia-server:ai \
      --ai /models/qwen2.5-7b-instruct-int4-ov --ai-device CPU
  ```

* **Who can reach it.** There is no access secret or rate limit yet: anyone who can reach the port can create documents
  (`--no-create` stops that). Keep it on a trusted network or behind a proxy that asks for a login.
