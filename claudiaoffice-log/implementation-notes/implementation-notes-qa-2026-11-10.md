# Quality round, 2026-11-10: every test, and whether CI works

Run against a fresh clone of `main` at `301ded6`. Findings and fixes are in `bugtracker.md` (UX-16 to UX-19,
PROC-04 to PROC-08, CODE-11, CODE-12, and status updates for CODE-02, CODE-05, CODE-09 and the items that had said
"patch ready, not yet committed" for days although they were in the tree).

## What was run

| Suite | Before | After |
|---|---|---|
| `check_debt.py --ci`, as CI's Python job runs it | failed: "e2e greeting" not allowed to skip | passes |
| `pytest` (2,969 tests) | 1 failure: a performance guard measuring the garbage collector | 2,960 passed, 9 skipped (Windows-only, OpenVINO) |
| web `vitest` (34 files) | 509 passed | 514 passed |
| web types, as CI ran them (`vue-tsc --noEmit`) | "passed", checking no file | CI now runs `nuxt typecheck` |
| `tests/e2e` (three servers, Chromium) | not run anywhere | passes |
| `web/e2e/*.cjs` (seven browser scripts) | all seven failed | all seven pass |
| Windows client: vitest, `tsc`, menu `--check`, tool tests | not run anywhere; 1 test and the menu check failed | pass |
| Linux client tests | 113 passed, 42 skipped here (this machine's PyGObject is broken) | unchanged; CI's `linux-client` job runs them with GTK |
| The server as Docker and the .deb install it (`uv sync --no-dev --package claudia-server`) | — | all three apps start and answer `/api/health` |

The browser scripts were the most useful part of the round. Six failed on selectors from before the connection
indicator and File ▸ Manage existed and one on a toast that said formulas were "not there yet"; once those were
brought up to date, they found four real bugs no unit test could have seen (UX-16 to UX-19).

## CI after this round

`ci.yml` has five jobs: `python` (the gate on Linux, Windows and macOS), `web` (vitest and a type check that checks),
`e2e` (new: Chromium, `tests/e2e`, then the seven scripts), `windows-client` (new, on Windows) and `linux-client`.
`deb.yml` and `docker.yml` use the same action versions as `ci.yml` now. The runs themselves could not be seen from
this session (no API access to the repository), so "should work" rests on running every step locally, not on a
green run.

## Suggestions, not done

* ~~**Three workspaces, one frame.**~~ and ~~**The versioning policy has gaps.**~~ Done the same day, see
  `implementation-notes-one-frame-and-versions.md`.
* **Dependencies.** `npm audit` in `web/` reports 2 critical (vitest 3 / tinypool, dev only; vitest 5 fixes them)
  and 12 moderate (nuxt's build tooling, no fixed nuxt 4 yet). SEC-08 (no audit in the gate or CI) is still open.
  Starlette warns that `TestClient` with `httpx` is deprecated in favour of `httpx2`.
* **`.gitlab-ci.yml`** runs `pytest packages/` only — no gate, no web types, no clients. Either align it with GitHub's
  or remove it.
* **Still open from earlier rounds:** coverage and a web linter (CODE-01), the `state.py` docstring (CODE-05).
