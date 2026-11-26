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
./start.sh              # Windows: start.cmd
```

starts one server for all three apps (D430) and prints how to find each in the browser:

| app | address | start and open it |
| --- | --- | --- |
| computes (tables) | http://127.0.0.1:8765/?app=computes | `./start.sh computes` |
| composes (text) | http://127.0.0.1:8765/?app=composes | `./start.sh composes` |
| creates (presentations) | http://127.0.0.1:8765/?app=creates | `./start.sh creates` |

Naming an app only chooses the page the browser opens; `./start.sh all` is the same as `./start.sh`. The sealed
documents are kept in `.claudia/documents/<app>` and the server's certificate and settings in `.claudia/state`
(`--dir DIR` puts both under `DIR/` instead); `./start.sh --help` lists all options. The first start builds the web
app (needs Node.js 22 or newer).

**With the AI model.** `./start.sh --ai` lets the AI user of computes and creates answer with the language model in
`ai-models/` (one folder, converted for OpenVINO; `--ai MODEL_DIR` names another, `--ai-device CPU` runs it without a
GPU). The first time, OpenVINO GenAI is added to the environment. The server loads the model once for both apps.
composes keeps the scripted stand-in until it has a lens for the model (E7.5). Without a model, `@ai` in creates says
that there is none.

Requires Python 3.14 exactly: `.python-version` makes `uv` use it even where a newer Python is installed (OpenVINO
GenAI publishes no wheels for 3.15 yet). Design notes: `docs/core-kernel.md`.

## Run with Docker

One image holds the server of all three apps and the web app. As with `./start.sh`, a container serves all three;
`CLAUDIA_APP` (`computes`, `composes` or `creates`) limits it to one.

```
docker build -t claudia-server .      # needs Docker 23 or newer (BuildKit)
```

Builds of `main` are also published by CI as `ghcr.io/claudiaoffice/claudia-server`, so `docker pull` can replace the build.

```
docker run -d --name claudia -p 8765:8765 -v claudia:/data claudia-server
```

Open https://localhost:8765/. The server makes its own certificate on first start, so the browser warns once.

* **Data.** `/data` holds the documents (`documents/<app>/`, each one sealed by its people's passwords) and the
  server's certificate (`state/`). The documents survive `docker rm` as long as the volume does; a volume is used by
  one container at a time (D435). A
  folder mounted instead of a volume must be writable by user id 10001 (`chown 10001:10001 DIR`).
* **Options.** Everything after the image name goes to the server, and `--help` lists it all: `--tls-name
  claudia.example.org` (the name people type), `--allow-host NAME` (another name the server answers to: without it
  a request that arrives under any name other than `localhost` or an IP address is refused, 403), `--no-tls
  --behind-proxy` (a TLS proxy in front), `--tls-cert` and `--tls-key` (your own certificate, mounted into the
  container), `--no-create`, `--no-list`, `--max-documents N`, `--shapes DIR` (creates).
* **Health.** The image checks `/api/health` itself; `docker ps` shows `healthy` once the server is up.
* **AI model.** The image has no language model runtime by default. For `--ai` (computes and creates use it) build
  with `--build-arg WITH_OPENVINO=true`, which makes the image about 270 MB larger, and mount a model folder. A
  container has no GPU unless you pass one in, so name the device:

  ```
  docker build --build-arg WITH_OPENVINO=true -t claudia-server:ai .
  docker run -d -p 8765:8765 -v claudia:/data -v ~/models:/models:ro claudia-server:ai \
      --ai /models/qwen2.5-7b-instruct-int4-ov --ai-device CPU
  ```

* **Who can reach it.** By default anyone who can reach the port can create documents, up to `--max-documents`
  (1000). To keep strangers out, set an access secret (`-e CLAUDIA_ACCESS_SECRET=...`, at least 16 characters): only
  those who know it can then create documents or read the list (the web app has no field for it yet, so it is for
  clients of the protocol for now), or use `--no-create`. See `docs/server.md`, *Who can reach the server*.
* **Who configures it.** The server settings (`/admin`) need an administrator. The first one is named with the *setup
  code* the server prints in its log at every start while it has none (`docker logs`; also in `admin/setup-code` of
  its state folder), or at start with `-e CLAUDIA_ADMIN=anna -e CLAUDIA_ADMIN_PASSWORD=...` (a password file instead:
  `--admin anna --admin-password-file FILE`). Locked out? Start it once with `--reset-administrators`: the
  administrators are forgotten, every setting stays. See `docs/server.md`, *The first administrator*.

### A web demo on a serverless platform (Scaleway)

For a demo that needs no storage, the same image runs on a serverless container platform with `CLAUDIA_DEMO=1`:
documents live in memory (at most 100, and gone whenever the container stops or scales to zero), nothing is written to
disk, and the server speaks plain HTTP because the platform encrypts in front of it (`--no-tls --behind-proxy`). The
server listens on the port in `PORT`, which the platform sets (Scaleway: 8080). One container serves all three apps.

| Environment variable | |
| --- | --- |
| `CLAUDIA_DEMO` | `1` |
| `CLAUDIA_APP` | optional: `computes`, `composes` or `creates` serves that app only |
| `CLAUDIA_ALLOW_HOST` | the name people type in the address bar, without `https://`, e.g. `abc123.functions.fnc.fr-par.scw.cloud` or your own domain; several separated by commas |
| `CLAUDIA_ADMIN`, `CLAUDIA_ADMIN_PASSWORD` | optional, as *secret* variables: the first administrator of the server settings. Without them every cold start prints a new setup code in the container's log, and only someone who reads it can name one |

Scaleway Serverless Containers, step by step:

1. Build for `linux/amd64` (Scaleway refuses other architectures, so on Apple silicon the `--platform` matters), push to
   a Container Registry namespace of yours:

   ```
   docker login rg.fr-par.scw.cloud/NAMESPACE -u nologin --password-stdin <<< "$SCW_SECRET_KEY"
   docker build --platform linux/amd64 -t rg.fr-par.scw.cloud/NAMESPACE/claudia-demo:latest .
   docker push rg.fr-par.scw.cloud/NAMESPACE/claudia-demo:latest
   ```

2. Create the container in a Serverless Containers namespace, with that image, the three variables above, privacy
   *public*, and these settings:

   | Setting | Value | Why |
   | --- | --- | --- |
   | Port | leave the default | the platform tells the server which one through `PORT` |
   | Min scale / max scale | 0 / **1** | documents are in the memory of one instance; with two, people would land on different ones and not see each other |
   | Memory | 1 GB | the server needs about 70 MB idle and a few MB per document |
   | Request timeout | the maximum, 3600 s | the live connection is one long request; the web app reconnects by itself when it ends |
   | Health check | **TCP**, not HTTP | the server refuses requests under names it does not know, and the name a platform's probe uses is not known in advance |

3. The platform gives the container its address only once it exists, so the first start has no `CLAUDIA_ALLOW_HOST`
   and every page answers *This server does not answer to the name you used*. Copy the address from the console
   (or from the log line *refused a request for the host '...'*), set it as `CLAUDIA_ALLOW_HOST`, and redeploy. A
   custom domain can be set from the start.

Things to know:

* After 15 minutes without traffic the container scales to zero and the demo documents are gone (min scale 1 keeps
  them, and costs).
* To keep strangers from filling the demo, set `CLAUDIA_ACCESS_SECRET` as a *secret* environment variable (see above).
* Scaleway's documentation does not say whether WebSocket connections are supported, and the apps cannot work without
  them. If the page loads but opening or creating a document fails, check the container log first, then ask Scaleway.

## Releases, image and demo (CI/CD)

GitHub Actions does the work (`.github/workflows/`):

| workflow | when | what |
| --- | --- | --- |
| `ci.yml` | every push to `main`, every pull request, weekly | tests of the Python packages, the web app and the Linux client |
| `docker.yml` | `main`, tags `v*`, pull requests (build only) | builds the server image, starts each app once as a test, pushes `ghcr.io/claudiaoffice/claudia-server` (`:latest`, `:sha-<commit>`, `:1.2.3` for tags) |
| `deploy-demo.yml` | after `docker.yml` succeeded on `main`; by hand | copies the image to the Scaleway registry and redeploys the demo containers; by hand it deploys any image tag, which is also the way back to an earlier version |
| `deb.yml` | `main`, tags `v*`, pull requests | builds `claudia-office_<version>_amd64.deb` (the three desktop apps, server, Python 3.14 and web app in one package), installs it on a clean runner and starts every app; on a tag the file is attached to the GitHub release |
| `macos.yml` | `main`, tags `v*`, pull requests, by hand | builds `claudia-office-<version>-macos-arm64.pkg` on Linux (the three apps, the uninstaller, the runtime and the optional service) and reads it back; on a tag the file is attached to the GitHub release. It cannot be installed in CI: `packaging/macos/test-install.sh` on a Mac (packaging/macos/README.md) |

To release: set the version in `clients/linux/src/claudia_shell_gtk/_version.py`, then tag `vX.Y.Z` and push the tag.
The set-up of the demo deployment (secrets and variables) is described at the top of `deploy-demo.yml`. Build the
package yourself with `packaging/debian/build-deb.sh` (it builds in `/opt/claudia`, which must be empty and writable).

