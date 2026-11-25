# Specs: what a person can do, written before it is built

**Status: in use since 2026-11-19 (D1241); pilot: the tables of composes.** The working agreement is in the project
instructions: before a feature is coded, its most important user behaviour is written here as Gherkin,
reviewed and approved by the owner, and only then are tests and code written against it.

## Why

Unspecified behaviour and "it renders, but nobody can use it" were slipping through: unit tests said the model was
right, and nothing looked at the page. A spec in a person's words, run against the real server and a real browser,
is the contract. The owner reviews scenarios, not code.

## Layout

| Path | What |
|---|---|
| `specs/<app>/<feature>.feature` | Scenarios of one feature (`composes`, `computes`, `creates`), in the words of a person using it. |
| `specs/objects/*.feature` | What all objects do alike in all three apps (turning, words in a box, …). |
| `specs/menus/*.feature` | What the menus, context menus and keys of all three apps do alike, on the web and the desktop. |
| `specs/invariants/*.feature` | Scenarios every object of a kind of thing must pass (a new kind of object adds one row to the `Examples`). |
| `specs/<app>/<feature>.review.md` | The questions the draft raises, each with a proposed default; the owner answers by crossing out or changing. Deleted when the questions are answered and the answers are in the feature file or the decision log. |
| `tests/e2e/specs/` | The step code (pytest-bdd, Python Playwright): `conftest.py` and one `test_<feature>.py` per feature file. |

A feature file starts with a `# title` comment line, then `Feature:`. Which test checks a scenario is said by a tag
(below), not by the place it lives.

## How to write a scenario

- **Behaviour in a person's words.** "I press Tab in the last box", not "the `<textarea data-box>` fires keydown".
  No selectors, ids, wire methods or timing in a scenario; those live in the step code.
- **One reason to fail per scenario.** Short, with `Then` steps a person could check by looking.
- **Comments** (`# …`) go on their own line, never behind a step.
- **Tags**, one vocabulary for all files:
  - `@core`: the journeys that must always work; run on every delivery.
  - `@extended`: edge cases and rarer paths; run before delivery and nightly.
  - `@firefox`: also run in Firefox (all `@core` should be). Chromium is the default.
  - `@two-users`: needs two browser windows.
  - `@desktop`: also to be driven through the GTK client (AT-SPI), later.
  - `@needs-decision`: the expected behaviour is a proposal; the scenario is skipped until the question in the review
    file is answered.
  - `@pending:<id>`: the behaviour is decided but not built (or somebody else builds it); the scenario is written and
    **expected to fail**. It is strict: when it passes, the run fails until the tag is taken off.
  - `@app:computes|composes|creates`: the apps a scenario runs in; none means all that the file's folder says.
  - `@e2e:<file>`: the browser test is a script in `web/e2e/`; `@unit:<path>` and `@io:<path>`: the scenario is tested
    by a unit or a file-format test because no browser is needed. These are not run by `tests/e2e/specs`.
  - `@draft` (on the `Feature:` line only): the file is a draft waiting for the owner's review. When the owner approves
    it, `@draft` comes off: the file is bound to step code in that commit, or waits in `NOT_BOUND_YET` (below) with its
    story until it is.
- **Defaults I propose are marked in the review file**, so that a reviewer only has to veto.
- **Every file is run, or says why not** (D1450). `tests/test_specs_are_bound.py` fails when a `.feature` file is not
  bound by a `test_<feature>.py`, its scenarios do not all carry `@unit:`, `@io:` or `@e2e:`, and it is not a `@draft`.
  An approved file that cannot be bound yet stands in that test's `NOT_BOUND_YET` with the story that binds it; the list
  only shrinks, and adding to it is the owner's call. In a file that runs, a test tag must name a test that exists and runs, and
  `@pending:<story>` a story that is not done.
- **A step that has no code skips its scenario**, with its words. The list of skips is the list of what the specs
  promise and the tests do not yet check; it is shown in every run.

## What every scenario run checks without being asked (the "always" steps)

Built into the step code (`tests/e2e/specs/conftest.py`), not repeated in the files, so that nobody can forget them:

1. No error in the browser's console, no uncaught exception.
2. A screenshot is kept at the end of each scenario (`.claudia/e2e/shots`), so that the person who reviews the run
   can look.
3. Where a scenario names things on the page, its step checks that they are really visible: they have a size and lie
   inside the text area.

Not built yet: errors of the server that the scenario did not expect, and "not covered by something else".

## Running them

`./run-e2e.sh --help` explains itself; `claudiaoffice-log/specs/running.md` has the same in a page. In short:
`./run-e2e.sh core` before every delivery, `./run-e2e.sh extended` for everything that is not waiting for a decision.

## Tooling (agreed 2026-11-19, D1241)

`pytest-bdd` with Python Playwright in `tests/e2e/specs/`, next to `live.py` (which starts real servers) and
`test_greeting.py` (which skips with a reason when the web app or a browser is missing). The existing
`web/e2e/*.cjs` scripts stay as they are; they are not rewritten.

Every bug fix starts with a scenario that fails; the commit that fixes it makes it pass.
