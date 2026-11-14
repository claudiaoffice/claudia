# Changelog of claudia-search

Newest first. The format follows [Keep a Changelog](https://keepachangelog.com/); versions follow the versioning
policy (`docs/versioning.md`). While the major version is 0, a minor version may break the API.

## [0.2.0] - 2026-11-14

Search & replace in composes and creates (E9.28, E10.19): a replacement that keeps more than the characters.

### Added
- `CompiledSearch.edits` and `Edit`: what replacing changes in a text, one edit per match (its number, where it is,
  what it says and what it becomes), and `apply_edits`. An app whose texts carry more than characters, such as who
  wrote which part of a paragraph, makes these edits one by one instead of setting the whole text.
- `Change.edits`: the edits that make the change (not part of the wire shape).
- `plan(leave=...)` takes `(at, number, said)` as well: `said` is what the match said when the person saw it. A text
  typed into since, whose match under that number now says something else, is skipped as `changed` instead of being
  replaced on numbers that moved.

## [0.1.0] - 2026-11-13

The search engine leaves the kernel and gets a clock (SEC-18, CODE-18, D287).

### Added
- The engine of `claudia_core.search` (`Query`, `Part`, `Condition`, `CompiledSearch`, `Match`, `SearchError` and the
  vocabularies `MODES`, `WHOLE`, `COMBINE`, `COUNTS`, `CONDITIONS`), moved here unchanged in what it accepts and what
  it compiles to. claudia-core imports the standard library only; the engine now needs `regex`.
- Patterns run on `regex` (version 0 syntax: Python's `re` syntax), which can be stopped. `CompiledSearch.matches`,
  `admits`, `left_out` and `replaced` take a `deadline` (a `time.monotonic()` time) and raise `SearchTimeout` once it
  has passed, inside a pattern too; without one a call may take `MAX_SECONDS` (1 s). Patterns such as `(a|a?)+!`, which
  took 12.5 s on 24 characters under `re`, are stopped at their deadline or, mostly, finish at once.
- `Text`, `scan`, `plan` and what they answer (`Scan`, `Hit`, `LeftOut`, `Plan`, `Change`, `Skip`): searching the texts
  of any document and planning a replacement, every place named by the app's own `at` (`Location`), with
  `location_key` for sets of places and `Refusal` for the app's say on a change. Both stop at a deadline and say
  `timed_out`. This is what was computes-only before (CODE-18).

### Removed
- The shape guard that refused patterns which "could backtrack without end" (`(a+)+`, `(a|aa)+`, …): it missed some
  exponential patterns and refused harmless ones; the deadline replaces it.

- Patterns are still read by `re` first, so the syntax stays Python's and a mistake is named as before (message and
  position); `regex`-only syntax such as `\p{L}` is refused for now.
