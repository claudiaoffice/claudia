# Contributing

## The rules of this repository

1. **Test first (TDD).** Write the failing test, watch it fail for the right reason, make it pass with the least code,
   then clean up. A change without a test that would have caught its absence is not finished. Bugs get a test that
   fails before the fix. Coverage only goes up: each Python package has a floor (`[tool.claudia.coverage-floors]` in
   `pyproject.toml`) and the web app's `app/lib` has thresholds (`web/vitest.config.ts`); when a change lifts one, raise
   it in the same commit (`uv run python scripts/check_coverage.py --ratchet` for the packages).
2. **Clean code.** Small functions with one job, names that say what things are, no comment that restates the code,
   no flag arguments that switch behaviour, no hidden state. Comments explain *why*. If code needs a long comment
   to be understood, change the code.
3. **The code is the documentation.** Every public class, function and method has a docstring; the API reference
   (`docs/`) is generated from them with Sphinx. Design decisions go to the decision log
   (`claudiaoffice-log/decision-log/`, one file per decision, numbers from `ranges.md`), not into code comments;
   stories go to the backlog (`claudiaoffice-log/Projects/claudia-office/_tasks/`). `claudiaoffice-log/README.md`
   explains both.
4. **APIs are versioned and documented.** What a package lists in `__all__` is its public API. A change to it needs a new
   version, a changelog entry and a regenerated snapshot (`docs/versioning.md`). The network API is versioned in its URL.
5. **Debt is looked for regularly.** `uv run python scripts/check_debt.py` runs lint, types, dead-code detection,
   the tests with their coverage floors, the docs build, the performance guards, the web app's lint, tests and
   types, and an `npm audit` of every lockfile (`scripts/check_npm_audit.py`: moderate or worse fails; what cannot be
   fixed goes into `[[tool.claudia.npm-audit-allow]]` in `pyproject.toml` with the reason). CI runs it on every push and once a week. A finding is fixed, or recorded in `vulture_whitelist.py`, the ruff
   config or `web/eslint.config.mjs` *with the reason*; it is never just silenced.
6. **The kernel stays pure.** `claudia-core` does no I/O, knows no app, and imports only the standard library
   (a test enforces it).

## Working

```
uv sync                                  # Python 3.14, creates .venv
uv run pytest                            # all tests
uv run pytest --cov && uv run python scripts/check_coverage.py   # and their coverage, against the floors
uv run python scripts/check_debt.py      # everything CI checks
uv run python scripts/check_debt.py --fast   # without the docs build and the performance guards
uv run sphinx-build -W -b html docs docs/_build/html
```

A pull request should be one idea, small enough to review in one sitting, with its tests, docs and changelog entry.
