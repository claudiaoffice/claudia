# Coverage floors and a web linter (CODE-01), and two leftovers

Branch `main`, 2026-11-10, at the owner's request after the one-frame round: delete `.gitlab-ci.yml`, do CODE-01. The
`state.py` half of CODE-05 came along because it was three lines.

## Python coverage

* `pytest-cov` in the dev group; `[tool.coverage.run]` in `pyproject.toml` measures `packages/*/src` (statements and
  branches), not the tests.
* The gate's `tests` step runs with `--cov`. On Python 3.14 coverage uses `sys.monitoring`, and the suite took no
  measurably longer (68 s with, 75 s without, on the same machine, back to back).
* `scripts/check_coverage.py` reads `.coverage` and compares each package with its floor in
  `[tool.claudia.coverage-floors]`. A package without a floor fails, and so does a floor for a package that was not
  measured; one that could go up by a whole point is named but does not fail. `--ratchet` raises floors to what was
  measured and never lowers one. Lowering a floor is done by hand, with the reason in the commit message.
  `tests/test_check_coverage.py` covers the decisions and one real data file.
* The first floors, rounded down from what the suite reached (stable over three runs):

  | package | floor | | package | floor |
  |---|---|---|---|---|
  | ai | 98 | | creates | 93 |
  | client | 88 | | creates-io | 88 |
  | composes | 83 | | fonts | 96 |
  | composes-io | 94 | | opc-io | 100 |
  | computes | 91 | | server | 92 |
  | computes-io | 95 | | test-documents | 89 |
  | container | 91 | | typeset | 87 |
  | core | 93 | | | |

* **Where the floors hold.** On Windows and macOS whole groups of tests skip by design (POSIX permissions, the real
  TeX engine), so a package would fall below a floor with nothing broken. The `coverage` check therefore runs on
  Linux with `xelatex`, `pdftocairo` and `kpsewhich` installed, and skips elsewhere, saying why. CI allows that skip
  only on its Windows and macOS runners (`runner.os != 'Linux'`), so a Linux run that stopped measuring would fail.
* A trap found on the way: a test that starts a second coverage measurement inside the suite's own stops the outer
  one, and every test after it goes unmeasured (two packages lost 1.5 and 3.5 points). The test that needs real
  coverage data makes it in a process of its own.

## Web lint

* ESLint 10 with `@nuxt/eslint-config` (Nuxt's recommended JavaScript, TypeScript and Vue rules), without the
  stylistic rules: the code's look is already consistent, and adopting a formatter is a separate decision.
  `npm run lint` (`--max-warnings 0`).
* It found 172 problems. Fixed: template self-closing and attribute order (autofix), `import type` forms, four late
  imports of the "Vue wiring" sections moved to the top, unused props and imports, a `v-for` variable named `ref`
  that shadowed Vue's `ref`, empty `catch` blocks in two e2e scripts, an unused variable in another.
* `any` is an error outside the tests. The one deliberate use is `WireData` in `protocol.ts`: a parsed frame before
  the code that knows its event or method reads it. It is written once, with the reason, and the sessions, the
  protocol client and the shell bridge use the name. `shell-bridge.ts` types the two globals it touches
  (`window.webkit`, `window.__claudiaShell`) instead of casting to `any`; `OpenDialog.vue` reads the error it catches
  through a narrow type.
* Turned off or narrowed, each with its reason in `eslint.config.mjs`: `no-dynamic-delete` (the sessions' state is
  plain reactive records keyed by id), `multi-word-component-names` for the four single-word components that
  predate the linter, and `no-explicit-any` in `tests/` (fakes of a socket, a shell or a frame).

## Web coverage

`@vitest/coverage-v8`; `npm run coverage` runs the unit tests and holds `app/lib` to 88% statements, 90% branches,
80% functions and 88% lines (`vitest.config.ts`). Only `app/lib` is measured: the tests run in Node without a DOM and
never mount a component; the browser scripts in `web/e2e` cover those. Vitest's own `autoUpdate` would write
fractional thresholds, so they are raised by hand.

## Where it runs

* `scripts/check_debt.py`: new checks `coverage` (after `tests`) and `web lint`; `web tests` now runs
  `npm run coverage`.
* CI: the Python job allows `web lint` to skip like the other web checks, and `coverage` off Linux; the `web` job
  runs `npm run lint` and `npm run coverage`.
* `.coverage` and `web/coverage` are ignored.

Checked: the full gate with `--ci` and no allowed skip at all (every check ran, including the browser test and the
Linux client), and all seven `web/e2e` scripts against fresh servers, because the autofix touched 34 components.

## Also in this round

* `.gitlab-ci.yml` deleted (GitLab is abandoned, `ci-cd.md`).
* CODE-05, `state.py`: its docstring said the folder holds the server's "encryption key and its TLS certificate".
  There is no server-wide encryption key (document keys live in memory only, `sealed.py`), and the folder also holds
  `admin/settings.json` and `admin/admins.json`. The docstring now lists what is there and why it is kept apart
  from the documents, and `--state-dir`'s help says the same.
