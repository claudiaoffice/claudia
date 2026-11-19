# Running the end-to-end tests on your computer

One command: `./run-e2e.sh`. It sets the computer up the first time (and only then), then runs what you ask for.
`./run-e2e.sh --help` says everything on this page.

## First time and every time

```
./run-e2e.sh setup            # only the setup: packages, the web app, browsers, fonts. Safe to repeat.
./run-e2e.sh setup --dry-run  # shows what it would do and changes nothing
```

You need `uv` and Node 22 (or newer) with `npm`; the script says what to install if one is missing. It does not use
`sudo`. It starts servers on ports 8765 to 8768, so stop a running `./start.sh` first (it checks).

## What to run

| Command | Runs | Takes |
|---|---|---|
| `./run-e2e.sh core` | the specs tagged `@core` (the journeys that must always work) | a few minutes once built |
| `./run-e2e.sh extended` | `@core` and `@extended`: everything in `specs/` that is not waiting for a decision | longer |
| `./run-e2e.sh regression` | what CI runs today: `tests/e2e` and the Node scripts of `web/e2e` | about 25–35 minutes |
| `./run-e2e.sh all` | regression, then every spec | the sum |
| `./run-e2e.sh --list` | what there is | instantly |

Options: `--browser chromium|firefox|both` (default chromium; the specs only, the older scripts are Chromium only),
`--feature tables` (spec files whose name contains it), `--only composes` (older scripts, repeatable), `--headed` (show the
browser), `--no-setup`, `--rebuild`, `--shots DIR`.

**Today** the specs are written and reviewed but their step code does not exist yet, so `core` and `extended` say so and
stop. `regression` works.

## Where the results are

- Screenshots: `.claudia/e2e/shots/` (one per script or scenario).
- Full output of every script: `.claudia/e2e/logs/`. When one fails, the last lines are shown on screen.
- The summary at the end lists every script with `ok` or `FAILED`, and says when tests were skipped (a skip is not a pass:
  for instance when no browser is installed).
- Exit status: `0` all passed, `1` something failed, `2` setup failed or a wrong option.

## When something goes wrong

- *"port 8766 is in use"*: a server is running (`./start.sh`?). Stop it.
- *A browser does not start on Linux*: it lacks system libraries. Run once the line the setup printed
  (`sudo … playwright install-deps chromium`).
- *Firefox does not run*: use `--browser chromium`; tell me what the log says.
- *Print tests fail and the setup said the fonts could not be fetched*: you were offline; run `./run-e2e.sh setup` again
  online.
- *Everything is stale*: `./run-e2e.sh regression --rebuild`.
