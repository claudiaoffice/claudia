# Test quality: no flaky tests, and tests that assert outcomes (PROC-63, PROC-66, D1660–D1662)

Branch `test-quality`, 2026-11-25. The owner asked for two things: no flaky tests any more, and a check of every test
for whether it asserts outcomes and contracts or implementation details (unit and API tests first; the Gherkin
scenarios worry him less). The yardstick was chapter 5 of *Build High Value Software Systems* (Leigh Griffin), "Testing
as waste prevention", and the line the owner added to coding standards §2 the same day ("Tests check behavior, not
implementation details … must not break").

## 1. Where the flaky tests were

**CI history.** The last 200 runs of `ci.yml` (2026-11-13 to 11-25): 145 failed. For every failed run the failing tests
were collected from the log, then sorted into *breakages* (one cluster of consecutive failures that ends when a fix
lands) and *flakes* (failures scattered over the history). Most were breakages: a snapshot not updated, a Windows path,
a tracker table out of step. The scattered ones were all bound to a clock:

| Test | Failures (clusters) | Systems | Cause | Now |
|---|---|---|---|---|
| `test_calculating_a_long_chain_is_linear` | 24 (16) | all | stopwatch ratio | counted, PROC-61 (`batch-3`) |
| `test_another_window_is_answered_quickly_while_a_password_is_hashed` | 13 (3) | all | ping < 50 ms while a hash takes 0.3 s | hash held (PROC-66) |
| `test_the_grid_is_on_the_screen_and_alternatives_and_following_work` (e2e) | 14 (3) | Chromium | counted before the page drew | already `expect(...).to_have_count` on `main` |
| `test_composes_starts_its_server_…_native_menu_drives_it` (GTK) | 8 (3) | Linux client | read before the page settled | not reproduced; left (see §5) |
| `test_the_server_dies_when_the_shell_is_killed_…` (GTK) | 2 (2) | Linux client | `/proc/<pid>/stat` read while the process exits raises `ProcessLookupError` | caught (PROC-66) |
| `test_a_real_server_stops_by_itself_once_nobody_uses_it` | 1 (1) | Windows | pipe full, see PROC-63 | `communicate()` |

**Under load.** The changed and the clock-reading test files were run three times while six busy loops loaded the two
cores of this workspace. That found what CI had not yet: `test_a_missing_document_costs_as_much_time_as_a_wrong_password`
(two stopwatches compared), and the search time-budget tests (0.6 s allowed for a 0.2 s deadline; 0.66–0.78 s measured)
in `claudia-search` (`test_engine.py`, `test_scan.py`), `claudia-computes` (`test_workbook_search.py`) and the server
(`test_server_computes.py`). After the fixes all of them passed three times under the same load. (A loaded run of the
whole suite was stopped after 35 minutes on one package; the whole suite ran unloaded, see §6.)

## 2. Every sleep in test code (PROC-66)

58 sleep calls in 28 files (test files and the `testing` modules; the sleeps inside child programs written as strings not counted). What each kind became:

| Kind | Where | Became |
|---|---|---|
| A nap for "the work has started by now" | model engine (2), AI router, AI runner (3), assistant, password methods | the work is **held** until the test lets it go; the test waits for `begun()` (D1660) |
| A nap for background rendering | rendering jobs (`settle()`, 20 uses), LaTeX fonts (2) | `await hosted.rendered()` (D1662) |
| A stopwatch on the event loop's pauses | gateway threads (2), release thread | the directory / the release is held; the test's own code running proves the loop ran |
| A nap so two timestamps differ | sealed store (newest first), suite listing | file times set with `os.utime`; one fake clock for both providers (D1662) |
| A nap and no check at all | hub `test_start_and_stop_run_the_housekeeping` | an idle document must be let go by the running sweep (it checked nothing before) |
| "Model is slow" + a time limit | AI runner (2) | `FakeModel(clock=FakeTime())`, `ModelRunner(clock=)`: the fake time passes, nobody waits |
| A wait for something that must not happen | open during release (new), Linux client shell kill, e2e setup-code field | kept, bounded, `# must not happen:` on the line |
| A poll's pace | sandbox, idle server, e2e start-up, GTK pump, … | kept; deadlines of 3 s and 5 s for a process to die raised to 10 s (a poll returns at once when it can) |
| A stand-in for slow work | `_nap` in workers, the hashing of `SlowDirectory`, the planning of `SlowEngine`, the injected pause of the desktop server, child programs in strings | kept, `# work:` on the line |
| A yield | heavy dispatch (`sleep(0)` ×14); workers (a 50 ms nap became `sleep(0)`: the first submission claims its slot before its first `await`) | kept (deterministic); see §5 |

`tests/test_no_sleeps_as_waits.py` holds every Python test file and the packages' `testing.py` fakes to this (a sleep is a yield, a poll's pace, or says
`# work:` / `# must not happen:`), with a test of its own that it finds a nap.

**Other clock-bound asserts** found by reading every test that reads a clock: COUNTIF over a million rows had to take
< 50 ms (now: the counted work of a million rows is that of ten); the TypeScript tests of the Neutralino core read a log
600 ms after starting a process (now `vi.waitFor` on the log), and one web session test waited 5 ms (now `vi.waitFor`).
Upper bounds that guard against "never" and sit far from the measured time were left: the layout library's 4 s and
6 s for 100 pages, 20 s for 4,000 names, 5 s for a SQL limit, 3–5 s in the Claude provider tests.

**Waste removed on the way.** The stalled-Anthropic test waited 30 s for the provider's read timeout on every run, and
every test with the fake Anthropic 0.5 s for its server to notice shutdown: the AI router's tests take 1.5 s instead
of 39 s, the claudia-ai tests 1.7 s instead of 9 s.

## 3. The audit: outcome or implementation?

**Method.** Every test function was parsed (7,416 Python test functions in 500 files; 2,622 TypeScript tests in 195
files) and flagged for: no check at all, checks of calls on a mock, `isinstance` assertions, reads of private
attributes, patches of private names, source inspection, and assertions that are only `is not None` or truthiness.
Every flagged test (236 Python) was then read; and 40 unflagged unit and API tests drawn at random were read to see
what the scan cannot.

**What the reading found.**

* The random sample: 40 of 40 assert outcomes: the model as people see it, the exported file, the refusal and its
  words, the wire answer, undo restoring what was. The suite is overwhelmingly outcome-based.
* **No check, 20:** all are "must not raise" contracts (stopping twice, releasing what is not open, a schema that
  validates). Correct as they are.
* **`isinstance`, 76:** almost all on a public result type (`Refused`, `NeedsTrust`, `ErrorValue`, `TypesetFailed`).
  Fixed: two that could not fail (`isinstance(x, (CommandApplied, object))`, `isinstance(SandboxError("x"),
  Exception)`); "without a model the assistant says so" checked the engine's class and now checks what it says; "a join
  that changes nothing about the item has the plain inverse" checked the inverse's class and now checks that undo brings
  both items back.
* **Private attributes, 101 tests:**
  * python-docx / python-pptx elements (`paragraph._p`, `run._r`, `shape._element`), 30: they read the *written file*,
    which is the contract with Word and PowerPoint. Kept.
  * method tables (`table._methods[...]`), 4: now read through `describe()`, which is what `/api/protocol` serves.
  * `provider._file("alpha")`: now the file's path in the folder.
  * **For decision** (missing public seams; listed for the owner, not changed): `WorkbookModel._calculate_loaded()` is
    called by three importers and about 20 tests (the import's "calculate what was loaded" has no public name);
    `Hub._documents.clear()` stands for a restart in the rendering and LaTeX tests (a new `Hub` on the same provider would
    be the public way); `WorkerPool._discard` / `._executor` are tested white-box for a race that a behaviour test cannot
    yet provoke; `KdfPolicy._calibrate` / `._set` are replaced in two tests; the Linux client's launcher and window tests
    read `server._app`, `window._bridge`.
* **Private names patched, 11:** fault injection and network stand-ins at private seams (`renewal._write_zip`,
  `starter._download`, `hyphenation._download`, `webfonts._woff2`, `formats._reader`, `i18n._lookup`, `crypto._now`,
  `paragraph._opcodes`, `_resolve_locale`), a limit made small (`_MAX_INFO_BYTES`), and the mutation test of the chain
  guard (`Round._precedents`, on purpose). They test outcomes but break when the private name is renamed: for decision.
* **Calls on a mock, 4 Python, 133 TypeScript:** in Python, three record what a fake pool was given (a port of the
  dispatcher: fine) and one checks that `start()` starts the KDF measuring (`Mock`, `assert_called_once_with`): wiring,
  for decision. In TypeScript the calls are on injected ports (a font loader asked for the slide font, a print callback
  called once, a shortcut running its command): the boundary of the module under test, not its insides. Kept.
* **Wiring tests:** `test_server_apps.py` asserts which method table and which engine class a model gets (`is
  computes_methods`, `{ScriptedEngine, TextEngine}`). They break on a rename, not on a wrong behaviour; the behaviour is
  covered by the app's own tests. For decision.
* **"must not break":** the owner's new rule has no mark in the code yet: no test carries it. A form is needed (a pytest
  marker, a `@must-not-break` Gherkin tag, a vitest name prefix) and a check that every story has one. For decision.

## 4. Each rewritten test was checked against its bug

The code was broken on purpose and the test had to go red (then the code was restored):

| Test | Code broken | Red with |
|---|---|---|
| password methods: another window answered while hashing | `Connection.hashing_for` returns `None` (hash on the event loop) | "set_details stopped the other window while it hashed" |
| sealed: a missing document costs what a wrong password does | the decoy hash for a missing document removed | the hashes differ |
| AI runner: the time limit counts from the start | the deadline taken when the question is asked | the third question timed out |
| gateway threads: checking a password does not block the loop | `Gateway._verify` calls the directory on the loop | "held work was never let go" |
| release thread: opening waits for the release | `housekeeping` without the open lock | "opened again while it was still being let go" |
| hub: the running housekeeping sweeps | the sweep task never created | "the housekeeping let go of the idle document" |
| suite: newest first | `MemoryProvider` stamps with the wall clock | wrong order |
| COUNTIF over a million rows | every position listed | "a million rows took 10284x the work of ten" |

The first version of the time-limit test passed with the broken code: the fake clock made each answer instant, so the
questions were never queued together. Holding the model until all three were asked fixed the test. That is why every
rewritten test gets this check.

## 5. The bugs the audit found, fixed the same day (owner's go-ahead)

PROC-67 (a stopped question cuts its read of a silent Anthropic), PROC-68 (the "must not break" mark and its check,
D1663), PROC-69 (`HeavyDispatcher.idle()`), CODE-106 (public seams instead of private access) and PERF-14 (counted work,
processor time where the cost is in C, D1661). Each is in `bugtracker-fixed.md` with its test.

What the second round learnt: counting is blind to work in C, and a mutant of `since()` that copied the whole history
with a slice passed the counted guard. Where the data lives in lists the clock backs the count up, in processor time,
which a busy machine does not inflate. Two "breaks on purpose" patches of private names stay (`Round._precedents`,
`paragraph._opcodes`): they are how a guard is proved, not how a behaviour is checked.

Still as it was: the GTK end-to-end test that failed in three clusters before run 101 (not reproduced here); the
Windows sandbox test's two seconds for a child to start; the remaining private reads of the Linux client's and the
document file's own tests (not part of CODE-106); the wiring tests of `test_server_apps.py` and the `Mock` of the KDF
start in `test_server_cli.py`.

## 6. What was run, and what could not be

Run here: the full gate (`scripts/check_debt.py`): clean, except the e2e greeting it skips without a built web app;
the changed test files three times under load; `./run-e2e.sh core` against the real server and web app in Chromium
(`CLAUDIA_CHROMIUM` set to the workspace's Chromium): 143 passed, 0 failed, 23 xfailed, 79 skipped (not automated yet,
or checked by a unit test). On CI (run 45685996787, started by hand on `test-quality`): every job green, Windows and
both browsers included; PROC-63's test passed on Windows.
After the second round (the five bugs): the gate clean again; `@core` in Chromium 143 passed, 0 failed; CI run
45702535120 on `test-quality` green in every job. Windows needed two more tries for PROC-67: `os.dup` does not copy a
socket handle there, and closing a response waits for the read that nothing wakes; the answer is now read in a thread
of its own and the connection given up in the background.
Not run: the macOS job (not part of those runs), the GTK tests on a display here, a screen reader.

## Assumptions

* PROC-63's cause is the pipe: not reproduced (Linux pipes hold 64 KiB); the fix removes the possibility either way.
* The search tests guard "a backtracking pattern does not run for ever"; 5 s is far from both the deadline and forever.
* `Hold` belongs in `claudia_ai.testing` because claudia-ai may not depend on claudia-core (D1660).
* The check takes any sleep inside a loop for a poll's pace; it does not check that the loop has a deadline.
