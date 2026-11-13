"""The gate's own verdict must be true: a skipped check is never reported as clean (PROC-02).

``verdict`` is the pure decision at the end of a gate run — given what each check did, what does the gate say and
does it exit non-zero? It never runs a subprocess, so these tests are fast and do not depend on what tools happen to
be installed. ``main`` is exercised once, end to end, against the real checks of a fresh environment: the web checks
skip here because ``web/node_modules`` is not installed in this checkout, and that is exactly the case ``--ci`` must
catch (the bug's own reproduction).
"""

import importlib.util
import sys
from pathlib import Path

SPEC = importlib.util.spec_from_file_location("check_debt", Path(__file__).parent.parent / "scripts" / "check_debt.py")
check_debt = importlib.util.module_from_spec(SPEC)
sys.modules["check_debt"] = check_debt
SPEC.loader.exec_module(check_debt)

Outcome = check_debt.Outcome


def test_all_ok_is_clean():
    failed, message = check_debt.verdict([Outcome("ruff", "ok"), Outcome("mypy", "ok")], ci=False, allow_skip=set())
    assert failed == []
    assert message == "everything is clean."


def test_a_failure_is_reported_and_never_called_clean():
    outcomes = [Outcome("ruff", "ok"), Outcome("mypy", "failed", "line 1: error")]
    failed, message = check_debt.verdict(outcomes, ci=False, allow_skip=set())
    assert failed == ["mypy"]
    assert message == "FAILED: mypy"


def test_a_skip_outside_ci_is_named_not_hidden_behind_clean():
    """The bug: a skipped check must never let the summary say the gate is clean."""
    outcomes = [Outcome("ruff", "ok"), Outcome("web tests", "skipped", "npm install needed")]
    failed, message = check_debt.verdict(outcomes, ci=False, allow_skip=set())
    assert failed == [], "a plain, non-CI run does not fail on a skip"
    assert message == "clean except skipped: web tests (npm install needed)"
    assert "everything is clean" not in message


def test_several_skips_are_all_named():
    outcomes = [Outcome("web tests", "skipped", "no node_modules"), Outcome("web types", "skipped", "no node_modules")]
    _, message = check_debt.verdict(outcomes, ci=False, allow_skip=set())
    assert message == "clean except skipped: web tests (no node_modules), web types (no node_modules)"


def test_ci_turns_an_unlisted_skip_into_a_failure():
    outcomes = [Outcome("web tests", "skipped", "no node_modules")]
    failed, message = check_debt.verdict(outcomes, ci=True, allow_skip=set())
    assert failed == ["web tests"]
    assert message == "FAILED: web tests"


def test_ci_accepts_a_skip_that_is_explicitly_allowed():
    """An allowed skip does not fail the build, but the summary still names it: an allowed skip is still a skip."""
    outcomes = [Outcome("linux client tests", "skipped", "the Linux client is checked on Linux")]
    failed, message = check_debt.verdict(outcomes, ci=True, allow_skip={"linux client tests"})
    assert failed == []
    assert message == "clean except skipped: linux client tests (the Linux client is checked on Linux)"


def test_ci_still_fails_a_real_failure_even_with_an_allowed_skip():
    outcomes = [Outcome("ruff", "failed", "boom"), Outcome("web tests", "skipped", "no node_modules")]
    failed, message = check_debt.verdict(outcomes, ci=True, allow_skip={"web tests"})
    assert failed == ["ruff"]
    assert message == "FAILED: ruff"


def test_parse_args_reads_ci_and_allow_skip():
    args = check_debt.parse_args(["--ci", "--allow-skip", "web tests", "--allow-skip", "web types"])
    assert args.ci is True
    assert args.allow_skip == {"web tests", "web types"}
    assert args.fast is False


def test_parse_args_defaults_are_off():
    args = check_debt.parse_args([])
    assert args.ci is False
    assert args.allow_skip == set()
    assert args.fast is False


def test_fast_still_parses_alongside_ci():
    args = check_debt.parse_args(["--fast", "--ci"])
    assert args.fast is True
    assert args.ci is True


def test_ruff_format_is_its_own_check():
    """CODE-08: the gate must run ``ruff format --check`` as a named check, not fold it silently into ``ruff``."""
    all_checks = check_debt.checks()
    assert "ruff format" in [c.name for c in all_checks]
    formatting = next(c for c in all_checks if c.name == "ruff format")
    assert formatting.command == ("uv", "run", "--quiet", "ruff", "format", "--check", ".")


def test_mo_compilation_is_its_own_check():
    """D160: the gate protects the Gtk client's compiled ``de`` catalog from drifting away from ``po/de.po`` now
    that there is real German translation worth drifting away from, the same way "i18n extraction" protects
    ``po/claudia.pot`` from drifting away from the source."""
    all_checks = check_debt.checks()
    assert "mo compilation" in [c.name for c in all_checks]
    mo_check = next(c for c in all_checks if c.name == "mo compilation")
    assert mo_check.command == ("uv", "run", "--quiet", "python", "scripts/compile_mo.py", "po/de.po", "de", "--check")


def test_the_servers_catalog_is_checked_like_the_shells():
    """D322: the server has its own compiled ``de`` catalog, and the gate keeps it in step with ``po/de.po``."""
    check = next(c for c in check_debt.checks() if c.name == "mo compilation server")
    assert check.command[-3:] == ("--locale-dir", check_debt.SERVER_LOCALE_DIR, "--check")


def test_i18n_merge_is_its_own_check():
    """A translation file that lacks a string the template has, or still holds one the code no longer uses, is
    caught by the gate, as the template itself is by "i18n extraction"."""
    merge_check = next(c for c in check_debt.checks() if c.name == "i18n merge")
    assert merge_check.command == ("uv", "run", "--quiet", "python", "scripts/update_po.py", "--check")


def test_ci_catches_the_real_bug_with_no_node_modules(tmp_path):
    """The acceptance test asked for in the finding: with no ``node_modules``, ``--ci`` exits non-zero.

    This checks it the cheap way, without running the whole gate: the real ``web_checks()`` pointed at a web folder
    without ``node_modules`` really does skip, and feeding that real skip through ``verdict`` under ``--ci`` with no
    allow-list really does fail. (It used to look at this checkout's own ``web/``, and so failed on every machine
    where somebody had run ``npm install``.)
    """
    checks = check_debt.web_checks(tmp_path)
    assert checks, "web_checks() must return the two web checks even when they will skip"
    outcomes = [check_debt.Outcome(c.name, "skipped", c.skip_reason) for c in checks if c.skip_reason]
    assert outcomes, "a web folder without node_modules (or a machine without npm) must make the web checks skip"
    failed, _ = check_debt.verdict(outcomes, ci=True, allow_skip=set())
    assert failed, "check_debt.py --ci must exit non-zero when node_modules is missing and no skip is allowed"


def test_the_browser_test_is_its_own_step_and_never_fails_the_gate_for_being_unrunnable():
    """UX-10's test needs a built web app and a Chromium, so it is a step of its own that skips with a reason.

    A skip is still named in the final line (PROC-02) and still fails ``--ci`` unless allowed, which is how CI says
    out loud that the dedicated ``e2e`` job is the one running it for real.
    """
    (check,) = check_debt.e2e_checks()
    assert check.name == "e2e greeting"
    assert check.slow, "it starts three servers and a browser; --fast should leave it out"
    if check.skip_reason:
        failed, message = check_debt.verdict(
            [check_debt.Outcome(check.name, "skipped", check.skip_reason)], ci=False, allow_skip=set()
        )
        assert not failed and check.name in message, "an unrunnable browser test is a named skip, not a failure"


def test_the_browser_test_does_not_also_run_inside_the_main_suite():
    """It starts three servers; the suite that runs on every save must not."""
    (tests,) = [c for c in check_debt.checks() if c.name == "tests"]
    assert "--ignore" in tests.command and check_debt.E2E in tests.command


def test_the_suite_measures_coverage_and_the_floors_are_their_own_check():
    """CODE-01: one run of the suite measures, and a check of its own holds each package to its floor."""
    names = [c.name for c in check_debt.checks()]
    (tests,) = [c for c in check_debt.checks() if c.name == "tests"]
    assert "--cov" in tests.command
    assert names.index("coverage") == names.index("tests") + 1, "the floors read what the suite just measured"


def test_the_coverage_floors_skip_where_tests_cannot_all_run():
    """Off Linux, or without TeX, whole groups of tests skip, so the floors would fail for nothing broken."""
    everything = lambda program: f"/usr/bin/{program}"  # noqa: E731
    assert check_debt.coverage_check("linux", everything).skip_reason == ""
    assert "Linux" in check_debt.coverage_check("win32", everything).skip_reason
    no_tex = check_debt.coverage_check("linux", lambda program: None)
    assert "xelatex" in no_tex.skip_reason


def test_the_web_app_is_linted_and_its_tests_held_to_their_coverage(tmp_path):
    """CODE-01: ESLint is a check of its own, and the web unit tests run with their coverage thresholds."""
    by_name = {c.name: c for c in check_debt.web_checks(tmp_path)}
    assert by_name["web lint"].command == ("npm", "run", "lint", "--silent")
    assert by_name["web tests"].command == ("npm", "run", "coverage", "--silent")


def test_the_layout_library_has_its_types_and_tests_checked(tmp_path):
    """D902: the TypeScript layout library is held to its own types (no DOM, no Node) and tests."""
    by_name = {c.name: c for c in check_debt.layout_checks(tmp_path)}
    assert by_name["layout types"].command == ("npm", "run", "typecheck", "--silent")
    assert by_name["layout tests"].command == ("npm", "test", "--silent")
    assert all(c.skip_reason for c in by_name.values()), "a layout folder without node_modules skips, saying why"
    names = [c.name for c in check_debt.checks()]
    assert names.index("layout types") < names.index("web lint")
