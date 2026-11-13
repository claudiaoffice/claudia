# npm audit: the findings fixed, and the audit in the gate and CI (SEC-08, 2026-11-11)

Base: `main` at `51c0f8d`. Reported by the owner: `npm warn deprecated glob@10.5.0 …` every time a desktop client
starts (`start-client.sh`, `start-mac-client.sh` and `start-win-client.cmd` all run `npm ci` in `web/`). Then: make it apply
to current main, and put the audit in the gate and CI.

## What was found

`npm audit` on `main`: **web 32** (2 critical, 28 moderate, 2 low), **clients/windows 4** and **clients/macos 4**
(each 2 critical, 2 moderate). The Linux client and the Python side have no npm packages.

| Source | Reached through | Runs where |
|---|---|---|
| `glob@10.5.0` (the warning) | `archiver-utils` (nuxt → nitropack → archiver) and `test-exclude` (`@vitest/coverage-v8`) | build, tests |
| `tinypool` ≤ 2.1.0, critical: prototype pollution leading to code execution | `vitest` 3 | tests (all three projects) |
| `@vitest/mocker` (path traversal, code injection) | `vitest` 3 | tests (all three) |
| `esbuild` ≤ 0.24 (any web page can query its dev server) | the two shells' own `esbuild` | build tools |
| `minimatch` < 11.0.1 (DoS) | `eslint`, `@eslint/config-array`, `typescript-estree`, `glob`, `readdir-glob` | mostly lint |
| `glob` 9–14.0.1 (AbortSignal bypass) | as above; 13.0.6 was affected too | build, tests |
| `node-forge` ≤ 1.4.2 (four advisories) | transitive via nuxt | dev server |
| `deepmerge` ≤ 4.3.1 (prototype poisoning, low) | `@rollup/plugin-node-resolve` → nitropack | build |

`archiver-utils@5.0.2` is the newest release and still asks for `glob@^10`, so a newer Nuxt cannot fix it: the
fix is an `overrides` entry. **Do not use `npm audit fix --force`:** its suggestion is `nuxt@4.1.3`, a downgrade.

## What changed

`web/package.json`: `nuxt` ^4.6.3 → ^4.6.4; `vitest` and `@vitest/coverage-v8` ^3 → ^5.1.0; `overrides` for `glob`
(^14.0.4), `minimatch` (^11.0.8) and `node-forge` (^1.4.3).
`clients/windows/package.json` and `clients/macos/package.json`: `vitest` → ^5.1.0 and `esbuild` ^0.24 → ^0.28.2
(vite 8, which vitest 5 needs, declares `esbuild ^0.27 || ^0.28` as a peer; both shells use only `build()`).
`web/vitest.config.ts`: coverage thresholds re-based (below). The three lockfiles were regenerated from the old ones,
not from scratch, so unrelated packages did not move.

Why the overrides are safe: `archiver-utils` calls only `require('glob')` and `glob.sync(...)`, and `glob@14` still has
both (checked by running it). Everything that still uses `minimatch` uses the named export (`{ minimatch }`), which
v10 and v11 share. A global `minimatch` override would break a dependent on the old v5 default-function style; none is
left in the tree (`readdir-glob` 3.0.0 asks for ^10).

## Result

| | before | after |
|---|---|---|
| web | 32 (2 critical) | **7 low**, one advisory: `deepmerge` |
| clients/windows | 4 (2 critical) | **0** |
| clients/macos | 4 (2 critical) | **0** |
| `npm ci` deprecation warnings | 2× `glob@10.5.0` | none |

The one advisory left (reported against `deepmerge` and the six packages that depend on it) has no patched release; it needs
untrusted input to reach `mergeObject()`, and here it runs at build time on our own config. It is below the audit's
level, so it needs no allow-list entry. Re-check when `deepmerge` or `nitropack` publishes a fix.

## The audit in the gate

`scripts/check_npm_audit.py`, a step of `scripts/check_debt.py` named `npm audit`, tested in
`tests/test_check_npm_audit.py` (against real `npm audit --json` output kept in `tests/data/`).

* **What it audits.** `web/package-lock.json` and every `clients/*/package-lock.json`, development tools included
  (`vitest` runs on every contributor's machine). Only the lockfile is read: no `node_modules`, only npm and the
  registry. A test walks the repository and fails if a `package-lock.json` exists that the audit would not reach, so
  the next npm project (the macOS client was one) cannot slip past.
* **What fails.** An advisory of **moderate or worse**; `--level high` narrows it. SEC-08 asked for high and critical;
  moderate was chosen because that is where 28 of the 32 findings were, and after this change there are none, so it
  costs nothing today. The trade-off: a new moderate advisory turns CI red for everyone until it is fixed or allowed.
* **The allow-list.** `[[tool.claudia.npm-audit-allow]]` in `pyproject.toml`, one entry per advisory (GHSA id), with a
  required `reason`. It is empty. Allowing one advisory does not hide another on the same package, and an entry that
  nothing needs any more fails the audit, so the list cannot rot.
* **When the registry cannot be reached** (no npm, no network, a timeout, output that is no report) the script exits
  with 3 after one retry and the gate records a **skip**: named in the summary, never "clean", and a failure under
  `--ci` (PROC-02). `Check` got a `skip_returncode` for this, because the gate only knew skips decided before a check runs.
* **Failure output** names each advisory with its package, severity, id, link and the direct dependency to update.

Checked against the real thing: on `main`'s original lockfiles the script exits 1 listing 19 advisories (web 9, each shell 5); on
this change it exits 0; with the registry address pointed nowhere the gate skips it (exit 0 locally, 1 under `--ci`).

## CI

No new job. The Python job already runs the gate with `--ci` on every push and every Monday, so the audit runs there
and a new advisory turns it red even when nobody pushed. It is not in that job's `--allow-skip` list, so it counts on
all three runners (three audits per run, a few seconds each). **Not verified here:** that run on the Windows and
macOS runners (the script finds `npm` with `shutil.which`, so it should work through `npm.cmd`). If it misbehaves
there, run the audit on Linux only, as the coverage floors do.

## Coverage thresholds: a decision, please look

`web/vitest.config.ts` keeps the floors "rounded down from what the tests reached". Under vitest 5 the same 545 tests
measure differently:

| | vitest 3 | vitest 5 | new floor |
|---|---|---|---|
| statements | 88.22 | 85.26 | 85 |
| branches | 90.99 | 82.38 | 82 |
| functions | 81.36 | 78.31 | 78 |
| lines | 88.22 | 86.94 | 86 |

Vitest 5 counts fewer statements (2369, was 3506), so the two are not comparable; no test was removed. CI's web job
runs `npm run coverage`, so it would fail on the old floors. The alternative is to stay on vitest 3 and accept the two
`tinypool` criticals and the `@vitest/mocker` advisories (tests only), in all three projects.

## How it was checked

On `main`'s tree with a clean `npm ci` in each project, Node 22.23 / npm 10.9.9:

* web: no warnings; `nuxt prepare`, lint, `npm run coverage` (35 files, 545 tests), `npm run typecheck`, `npm run build`.
* clients/windows: 63 tests, typecheck, `tsc`, `tools/build-inject.mjs`. clients/macos: 333 tests, typecheck, `tsc`,
  `tools/build-shell.mjs` (all three apps).
* the whole gate, `uv run python scripts/check_debt.py`: every step ok, with the web checks running, except
  `e2e greeting`, skipped for want of Chromium.

**Not run:** the Playwright e2e scripts, CI itself, macOS or Windows.

## Things to know

* `vitest@4.1.12` also fixes the advisories, but npm 10.9.9 crashes resolving it beside the overrides (`Cannot read
  properties of null (reading 'edgesOut')`, an arborist bug); 5.1.0 resolves cleanly.
* `nuxt@4.6.4` declares `node ^22.22.3 || ^24.15.0 || >=26`; vitest 5 `^22.12`. CI uses `"22"` (the latest 22.x), fine;
  an older 22.x prints an engine warning.
* A fresh clone needs `npx nuxt prepare` before `npm test` in `web/` (CI does it); without the generated `.nuxt` files
  every test file fails to load with `Tsconfig not found`, on the old and the new dependencies alike.
* **CI has no job for the macOS client**: `clients/macos` has 333 tests and a lockfile, and only the audit looks at it
  in CI. A job like `windows-client`, on a macOS runner, would close it.

## Follow-ups (not done)

* The same for Python: `pip-audit` (or `uv pip audit`) against `uv.lock`, the other half of SEC-08.
* A macOS client job in CI (above).
* Remove the `overrides` entries when `nitropack`/`archiver-utils` move to `glob` ≥ 14 and `eslint`'s tree to
  `minimatch` ≥ 11; the audit itself will not say so, so look when it is next touched.
