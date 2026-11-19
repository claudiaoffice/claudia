# Specs: what a person can do, written before it is built

**Status: draft of 2026-11-19, pilot on branch `e2e` (composes tables). Not yet agreed.** The working agreement is in
the project instructions: before a feature is coded, its most important user behaviour is written here as Gherkin,
reviewed and approved by the owner, and only then are tests and code written against it.

## Why

Unspecified behaviour and "it renders, but nobody can use it" were slipping through: unit tests said the model was
right, and nothing looked at the page. A spec in a person's words, run against the real server and a real browser,
is the contract. The owner reviews scenarios, not code.

## Layout

| Path | What |
|---|---|
| `specs/invariants/*.feature` | Scenarios every object of a kind of thing must pass (a new kind of object adds one row to the `Examples`). |
| `specs/<app>/<feature>.feature` | Scenarios of one feature, in the words of a person using it. |
| `specs/<app>/<feature>.review.md` | The questions the draft raises, each with a proposed default; the owner answers by crossing out or changing. Deleted when the questions are answered and the answers are in the feature file or the decision log. |

A feature file belongs to a story in `Projects/claudia-office/_tasks`; the story's acceptance lists the file.

## How to write a scenario

- **Behaviour in a person's words.** "I press Tab in the last box", not "the `<textarea data-box>` fires keydown".
  No selectors, ids, wire methods or timing in a scenario; those live in the step code.
- **One reason to fail per scenario.** Short, with `Then` steps a person could check by looking.
- **Tags**
  - `@core`: the journeys that must always work; automated first, run on every push.
  - `@extended`: edge cases and rarer paths; automated after `@core` is green.
  - `@firefox`: also run in Firefox (all `@core` should be). Chromium is the default.
  - `@two-users`: needs two browser windows.
  - `@desktop`: also to be driven through the GTK client (AT-SPI), later.
  - `@needs-decision`: the expected behaviour is a proposal; the scenario is not automated until the question in
    the review file is answered.
- **Defaults I propose are marked in the review file**, so that a reviewer only has to veto.

## What every scenario run checks without being asked (the "always" steps)

Built into the step code, not repeated in the files, so that nobody can forget them:

1. No error or warning in the browser console, no uncaught exception, no error toast.
2. No connection error or `command_error` from the server that the scenario did not expect.
3. Everything a scenario names is really visible: it has a size, it lies inside the visible area, it is not covered
   by something else. ("Four rows in the page" is not enough if only one can be seen.)
4. A screenshot is kept at the end of each scenario (and on failure), so that the person who reviews the run can look.

## Tooling (proposal, see the review file for the question)

`pytest-bdd` with Python Playwright in `tests/e2e/`, next to `live.py` (which already starts real servers) and
`test_greeting.py` (which already skips with a reason when the web app or a browser is missing). The existing
`web/e2e/*.cjs` scripts stay as they are; they are not rewritten.
