---
id: D762
title: "Actions are pinned by commit, and :latest and :main follow a green CI"
status: current
applies-to: all
date: 2026-11-17
round: "Stabilisation of main, second round (CODE-58, CODE-60, PROC-27)"
supersedes: []
superseded-by: []
---

# D762 · Actions are pinned by commit, and :latest and :main follow a green CI

**Pinned.** Every action of somebody else in `.github/workflows` is `owner/repo@<40 hex> # v<version>`. A tag moves; a
commit does not, and the workflows run with `packages: write` and the demo's secrets in reach. Dependabot (the
`github-actions` entry) reads the comment and proposes the next pin; `test_ci_workflow.py` fails for a loose one.

**Promoted.** `docker.yml` runs beside CI and pushes only `sha-<short>` (and the release tags). `promote-image.yml`,
started by a successful CI run on a push to main, waits for that commit's image and points `:latest` and `:main` at it
(`docker buildx imagetools create`: no second build). The demo deploys the same image after CI too (PROC-25).

**Scanned.** `codeql.yml` (Python and TypeScript, on every change and weekly) and a `pip-audit` job in `ci.yml` over
`uv export --frozen` (the Python half of SEC-08).

**Needs the owner on GitHub:** Code scanning must be switched on for the repository (Settings ▸ Code security), and the
"default setup" of CodeQL, if enabled, switched off, or the two clash. The first runs of the new workflows have not been
seen: this was written without access to Actions.
