# Claudia coding standards

Applies to all code in this repository: Python packages, the TypeScript/Nuxt web client, native clients, scripts and CI.

Claudia holds people's work. When priorities conflict, they rank in this order: do not lose or leak a user's data, be correct, be maintainable, be fast.

## How to read this document

Every standard has three parts:

- **Rule**: what we do.
- **Enforced by**: the tool, CI job or review step that makes the rule real.
- **Status**: `Enforced` (CI fails when the rule is broken), `Partial` (some of it is automated), or `Planned` (reviewed by hand until automated; each Planned item has a backlog entry).

A rule that nothing enforces will erode, so every `Planned` item is a debt item, not a wish.

**Exceptions** are recorded where the rule is enforced (a per-file ignore, a `noqa`, a whitelist entry) with a comment giving the reason and the condition under which it goes away. An exception that changes behaviour or architecture also gets a decision-log entry.

**Precedence**: decision log, then this document, then habit. If a decision contradicts this document, fix the document in the same patch.

---

## 1. Automated formatting, linting and type checking

**Rule.** One formatter and one linter per language, configured in the repo and run identically on a developer machine and in CI. Style is never discussed in review; the tool decides.

- Python: Ruff (formatting and linting, config in `pyproject.toml`), mypy, Vulture (dead code).
- TypeScript and Vue: one linter, one formatter and strict type checking (`tsc`/`vue-tsc`), chosen by decision and then pinned.
- One command runs the whole gate locally and is the same command CI runs. The Python gate runs on Linux, Windows and macOS.
- Tool versions are pinned. A tool upgrade is its own patch, so formatting churn never hides in a feature patch.
- Every suppression (`# noqa`, `# type: ignore`, per-file ignore, Vulture whitelist entry) carries a reason. Unused suppressions fail the build.
- New code is fully typed. Public functions have type hints and docstrings.

**Enforced by.** Ruff, mypy, Vulture in CI.
**Status.** Python: Enforced. Unused-ignore detection: Enforced for mypy. Full typing of new code and public docstrings: Planned (adopt per package with a ratchet, as for coverage). TypeScript lint, format and strict type check: Planned.

## 2. Tests

**Rule.** Tests are part of the definition of done and are written with the code, not after it.

- **Specs first for user-visible behaviour.** Before coding, the behaviour is written as Gherkin scenarios in `claudiaoffice-log/specs`, in user language and without selectors, tagged `@core` or `@extended`, and reviewed by the owner. Tests are written against the approved scenarios.
- Tests check behavior, not implementation details. They assert truths that stay true under safe refactoring. For every feature, there is at least one test that covers the key risk that the feature might not behave as intended. We mark this test as "must not break", naming its story (D1652, with the story of D1663):
  - **Python:** the pytest marker `@pytest.mark.must_not_break("E7.11")`, registered in the project's `pyproject.toml`; `pytest -m must_not_break` runs them all.
  - **Gherkin:** the tag `@must-not-break:E7.11` on the scenario.
  - **TypeScript (vitest):** `[must not break: E7.11]` in the test's title; `vitest -t "must not break"` runs them.
  - The test's docstring or comment names the risk it covers, in a sentence ("The key risk of …: …").
- **Every bug fix starts with a failing scenario or test.** The patch notes give a one-line reason it escaped: spec gap, missing test, or test passed but wrong. The reason feeds the invariants list.
- **Shared invariants suite.** Every object type passes the same generic scenarios: rendered exactly once, can be clicked into and typed in, survives reload, visible to a second user, undo/redo and a history entry, export/import round trip, reachable by keyboard alone, no console errors.
- **Test pyramid.** Many fast unit tests, fewer integration tests, and a few journey tests that run against the real server and web client (Playwright, Firefox first, GTK client checked as well). Journey tests fail on console errors and assert DOM counts; screenshot baselines are kept to a few. Gherkin is used only for user-visible behaviour, not for internals.
- **Coverage floors per package** are stored in the repo and may only go up (ratchet). A new package starts with a floor no lower than the lowest existing floor and is raised as it matures.
- **Deterministic tests.** No real network, no wall clock, no unseeded randomness, no sleeps as synchronisation. A flaky test is a size-2 bug: fixed or deleted within one week, never ignored.
- Before a patch is delivered, the author runs the "use it before delivery" journey against the real running server and web client, looks at the result, and states in the patch notes what was verified and what could not be run.

**Enforced by.** pytest, pytest-bdd, Playwright, the coverage check script with its ratchet, review of the scenarios, `tests/test_no_sleeps_as_waits.py` (a test waits for the thing, not the clock: D1660), `tests/test_must_not_break.py` (every story that is done has a marked test of its key risk: D1663).
**Status.** Unit and BDD tests, coverage floors with ratchet: Enforced. Journey suite, invariants suite and console-error failure: Partial. Flaky-test policy: Partial (no sleeps as waits in Python tests is checked; the one-week rule is kept by hand). "Must not break" marks: Partial (the form and `tests/test_must_not_break.py`; the 46 stories done before the rule wait for the owner to name their test).

## 3. Modules, boundaries and layering

**Rule.** Modules have explicit boundaries and a small public surface. Dependencies point in one direction, there are no cycles, and internals are private by default (underscore prefix, explicit `__all__`).

- Layering, from bottom to top: shared packages (`claudia-core` and other shared libraries), then the app modules (composes, computes, creates), then the server that hosts them. App modules do not import each other; anything two apps need moves down into a shared package.
- Clients (web, GTK, Neutralino shells, iOS) talk to the server only through the versioned public API. They never import server internals.
- Behaviour exists once. Logic that every client needs lives in the server or in a shared TypeScript library, not copied per client. This is how web and desktop clients stay identical in function.
- The layout and pagination library is written once, in TypeScript, and must run without a browser DOM so the server can use it later for printing and PDF export.
- Platform-specific code lives in clearly named modules (as with the Windows-specific typesetting code) and never leaks into shared code paths.

**Enforced by.** An import-contract check in CI (import-linter or equivalent) with the layering written down as contracts; for TypeScript an equivalent boundary rule in the linter.
**Status.** Planned.

## 4. Versioned interfaces and compatibility

**Rule.** Public interfaces are versioned and documented, and breaking changes are deliberate.

The interfaces in scope are: the server API used by clients, the `.claudia` document file format, the protocol between the document server and the AI server, the command and history log format, and the shared catalogue of translatable strings.

- Semantic versioning. The API version is part of the handshake or URL, and the server states which client versions it supports.
- A file carries its own format version. A reader that meets a newer version than it supports refuses cleanly; it never opens and rewrites the file.
- **Before the first stable release**, breaking changes are allowed, but each one is recorded in the decision log and the changelog, and migrating old documents is not required.
- **From the first stable release**, deprecation follows three steps: announce (docs and changelog), warn (runtime warning), remove. At least one minor release separates the steps. Any change to the container or log format ships with a migration and tests that use fixture files from every released version.
- Reference documentation is generated from the code (Sphinx for Python, TypeDoc for TypeScript), including the versioned API. The docs build fails on warnings.

**Enforced by.** Docs build in CI; compatibility tests with fixtures; review.
**Status.** Docs generation: Partial. Warnings-as-errors, API version handshake, format fixtures: Planned.

## 5. Readable code

**Rule.** Write code to be read: small functions, honest names, comments that explain why.

- Each function does one thing. Names use the vocabulary of the glossary (`glossary.md` in `claudiaoffice-log`) consistently in code, tests and UI. A new domain term is added to the glossary in the same patch.
- Complexity and size are limited by the linter, not by taste: the Ruff `PL` rules cap statements and branches per function, and cyclomatic complexity (`C901`) is enabled with a project maximum.
- No commented-out code and no dead code. Unused code is deleted, not whitelisted.
- Every Ruff rule we switch off is listed in `pyproject.toml` with the reason. A rule we ignore without a reason is a rule we have not decided about.
- Prefer deep modules: a small, stable interface hiding a lot of behaviour, over many shallow pieces that leak their internals.

**Enforced by.** Ruff, Vulture, review.
**Status.** Statement and branch limits: Enforced. `C901`, commented-out-code rule and reasons for ignored rules: Planned.

## 6. Errors, logging and privacy

**Rule.** Handle errors explicitly and consistently, and never let diagnostics break the privacy model.

- **One strategy per language.** Python uses exceptions from one small hierarchy of domain errors rooted in a shared base class; TypeScript uses typed error results at the API boundary. No bare `except`, no silently swallowed errors, no error used as control flow across a module boundary.
- **Validate at every boundary**: client requests, imported files, network input and AI output. AI output is untrusted input. It is validated and applied as recorded commands under the rights of the person who asked.
- **Retry only what is safe.** Only idempotent operations are retried automatically, with a cap and back-off. Everything else surfaces the failure.
- **User-facing errors** are translated, say what happened and what to do next, and never show stack traces.
- **Structured logs with correlation ids** let us follow a request across the server, workers and AI server.
- **Logs never contain**: document content, passwords, keys, the access secret, or user names and identifiers that people outside the document's user base must not see. Diagnose with ids and metadata, not content. This replaces the idea of debugging production from logs alone.
- **Audit events** (every export including PDF and print, failed logins, role changes, key rotation, redaction) are recorded as a separate audit stream, not mixed into diagnostic logs.

**Enforced by.** Review, tests that assert audit events, a log-content test that runs the E2E journeys and scans logs for planted secrets and names.
**Status.** Planned (the log-content test is the most valuable first step).

## 7. Security and dependencies

**Rule.** Security and dependencies are a standing practice, not a release-time check.

- Never commit secrets. Secret scanning runs in CI.
- **No homemade cryptography.** Use vetted libraries only. Any change to the document file, key slots, key derivation, signing or authentication needs a short threat note in the implementation note and a second look in review.
- **Imported office files are untrusted input.** Parsers apply limits (size, nesting depth, decompression ratio), do not resolve external entities, and never execute macros or fetch external resources.
- Dependencies are locked and pinned. Python and npm advisories are scanned automatically; npm audit already fails the build on moderate or higher.
- Each allowed advisory exception names the advisory and the condition for removing it.
- **Adding a dependency** needs a line in the patch notes: why it is needed, what the alternative was, that it is maintained, and that its licence fits the licence chosen for the component using it. Fonts and other assets are covered by the same rule.
- Container images are built and pushed only by the CI workflow, never by hand.

**Enforced by.** npm audit script, Python audit, secret scanner, licence check, review.
**Status.** npm audit: Enforced. Python audit, secret scanning, licence check, parser limits tests: Planned.

## 8. Decision records

**Rule.** We record decisions and the reasoning behind them, because the question "why did we do it this way?" comes up constantly in a large project.

- Every decision is one file in `claudiaoffice-log/decision-log/`, named `<id>-<status>-<applies-to>-<short-description>.md`. Status is `undecided`, `current`, `blocking` or `superseded`. Applies-to is `creates`, `computes`, `composes` or `all`.
- Decision id ranges are allocated in `claudiaoffice-log/decision-log/ranges.md` before work starts. The first patch of a piece of work is committed straight away, because it reserves the ids.
- A decision that was only discussed counts as made once it is written up. Written-up happens in the patch that implements it, and a feature is not done while its decisions live only in a chat.
- A superseding decision links to the one it replaces, and the old file's status changes to `superseded`.
- Code that exists because of a non-obvious decision cites the id in a comment, for example `# D251`.

**Enforced by.** Review; a CI check that every id referenced in code exists in the log and that file names follow the pattern.
**Status.** Convention in use: Enforced by review. CI check: Planned.

## 9. Technical debt

**Rule.** Pay down technical debt continuously, and measure it so it cannot grow unnoticed.

- **Ratchets, not targets.** Each metric has a recorded baseline and may only improve: coverage floors, Vulture findings, complexity maximum, duplication, CI wall time, and test runtime. A regression fails the build; the baseline is raised only in a patch that explains why.
- Dead-code whitelist entries need a reason and may not grow silently.
- **Reserved capacity**: at least one in five backlog items per milestone is debt reduction or tooling.
- Debt found while working is logged in the backlog with a size, not left in a comment. Bugs are reported by size: 1 (huge) to 3 (small).
- Duplication, unused code and slow code are checked on a regular schedule, not only when someone notices.

**Enforced by.** The coverage ratchet, Vulture, and (to add) duplication and CI-time checks.
**Status.** Coverage and dead code: Enforced. Complexity, duplication, build and test time: Planned.

## 10. Change workflow and definition of done

**Rule.** Work arrives as small, reviewable patches and `main` stays releasable.

- Work happens on a feature branch that includes the latest `main`. Patches are delivered against the branch the owner names, and only as patches, never as bundles. The last step before delivery is merging the latest `main` into the branch and checking that it is mergeable.
- Git identity: "claudia guy", `hello@claudia-office.de`. Commit messages are in the imperative and cite the backlog item or decision id.
- Every patch carries: the decision-log entry, the implementation note, the updated spec, a list of assumptions made, bugs found (with size), and a "what could not be run" statement.
- **Done means**: all tests pass including E2E and a "use it before delivery" run; the branch merges cleanly into `main`; all desktop clients work with the latest server; web and desktop clients do not diverge in functionality; import and export to other office formats work for the new feature; translation is complete and used in the UI; BITV deviations are listed; and the author reports on each of these points.
- Every patch is reviewed against this document before it is merged.

**Enforced by.** Review checklist derived from this section, branch protection, CI.
**Status.** Partial.

## 11. Internationalisation

**Rule.** All user-visible text is translatable from the first line of code.

- The gettext `.po` files are the single source of truth for interface text and short tooltips. The web client's JSON catalogue is generated at build time and is never edited by hand.
- No literal user-visible strings in code. Sentences are never built by concatenation; use placeholders and plural forms.
- Layouts tolerate longer text (German is routinely 30% longer than English). The locale is a client-side setting, detected by default and overridable in Config.
- A feature is not done while any of its menu entries, labels, tooltips or error messages is untranslated.

**Enforced by.** A CI check for missing or stale catalogue entries and for literal strings in UI code.
**Status.** Planned.

## 12. Accessibility and UI consistency

**Rule.** The three apps and all clients behave as one product, and everyone can use it.

- BITV 2.0 is the target. Conformance is judged by principle, and every patch lists where it diverges from the standard.
- Everything is operable by keyboard. Information is never carried by colour alone (this matters for purpose tints and chart colours). Controls expose accessible names; decorative objects are marked decorative.
- Menus and shortcuts come from the menu workbook (`claudia-menus`) and are identical across apps and clients, in the native menu bar, the web menu and the context menus. Every menu entry has a shortcut. If a new entry does not clearly belong somewhere, the owner is asked.
- UI follows the GNOME Human Interface Guidelines and the project design language. Web UI is checked in Firefox as well as Chromium.

**Enforced by.** Automated accessibility checks inside the Playwright journeys; a script that compares the menu definitions in code against the workbook; review.
**Status.** Planned (menu-versus-workbook script and accessibility checks); review: Enforced.

## 13. Data integrity and document compatibility

**Rule.** A person's document is never lost, corrupted or silently changed.

- Writes are atomic (write a temporary file, then rename, or use a transaction). A crash at any point leaves the previous valid state intact.
- History is append-only. The only exception is the explicit redaction feature, which is itself recorded.
- **Import and export are core features.** Each supported format (OpenDocument and the MS Office formats) has round-trip tests, and a new feature is not done until its import/export is tested.
- Import preserves what Claudia does not model, wherever possible. Where something cannot be kept, the user gets a report of what was lost; content is never dropped silently.
- A corpus of real-world documents is kept as test input, with anonymised or permitted files only.
- Exports and imports of unencrypted content follow the rules in the decision log and are logged.

**Enforced by.** Round-trip and corpus tests in CI, crash-injection tests on the write path.
**Status.** Partial (round-trip tests for the formats supported so far, to be confirmed; corpus and crash-injection tests Planned).

## 14. Performance, scale and determinism

**Rule.** Behaviour is deterministic and has measured performance budgets.

- **Determinism.** Every document renders identically wherever it is rendered. Pagination does not depend on browser layout. Layout is checked with golden tests, not by eye.
- **Budgets.** Each feature states its performance budget for an empty, a typical and a huge document, and a CI check protects the hot paths (open, type, scroll, recalculate, export).
- **Server execution.** The server's event loop is never blocked by CPU-heavy work, which goes to the shared worker pool. State-changing operations on one document are serialised; independent documents proceed independently; background results are validated against the current revision before they are applied; interactive work has priority over background work. (Proposed; becomes binding when the execution-model decision is made.)
- Optimise only with a measurement, and put the measurement in the patch notes.

**Enforced by.** Golden layout tests, performance tests on hot paths, load tests before release.
**Status.** Planned.
