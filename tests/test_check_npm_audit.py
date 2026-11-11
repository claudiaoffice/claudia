"""The npm dependency audit in the gate (SEC-08): known vulnerabilities fail it, an allowed one needs a written reason.

``advisories``, ``judge`` and ``read_allowlist`` are the pure decisions of ``scripts/check_npm_audit.py``. They are read
against ``tests/data/npm-audit-web-2026-11-11.json``, what ``npm audit --json`` really printed for ``web/`` that day
(32 findings, two critical), so the parser is held to the real format and not to one made up here. Nothing in this file
talks to the network: ``run_audit`` and ``main`` are given a stand-in for npm.
"""

import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).parent.parent
SPEC = importlib.util.spec_from_file_location("check_npm_audit", ROOT / "scripts" / "check_npm_audit.py")
audit = importlib.util.module_from_spec(SPEC)
sys.modules["check_npm_audit"] = audit
SPEC.loader.exec_module(audit)

CHECK_DEBT_SPEC = importlib.util.spec_from_file_location("check_debt", ROOT / "scripts" / "check_debt.py")
check_debt = importlib.util.module_from_spec(CHECK_DEBT_SPEC)
sys.modules["check_debt"] = check_debt
CHECK_DEBT_SPEC.loader.exec_module(check_debt)

REAL = json.loads((ROOT / "tests" / "data" / "npm-audit-web-2026-11-11.json").read_text(encoding="utf-8"))
GLOB_ADVISORY = "GHSA-3g3m-2fjr-6pw4"  # the one behind "npm warn deprecated glob@10.5.0"
TINYPOOL_ADVISORIES = {"GHSA-5gmw-xhrv-c9v3", "GHSA-85c8-ppgw-ccpr"}


def advisory(severity="high", package="left-pad", ident="GHSA-aaaa-bbbb-cccc", title="It breaks"):
    return {
        "source": 1,
        "name": package,
        "dependency": package,
        "title": title,
        "url": f"https://github.com/advisories/{ident}",
        "severity": severity,
        "range": "<2.0.0",
    }


def report(*vulnerable):
    """A tiny ``npm audit --json`` report; each item is ``(package, via: advisories or names, effects, is direct)``."""
    return {
        "auditReportVersion": 2,
        "vulnerabilities": {
            name: {"name": name, "severity": "high", "isDirect": direct, "via": via, "effects": effects}
            for name, via, effects, direct in vulnerable
        },
    }


# -- reading what npm prints -------------------------------------------------------------------------------------------


def test_the_real_report_yields_each_advisory_once_with_its_id_and_severity():
    found = {a.ident: a for a in audit.advisories(REAL)}
    assert GLOB_ADVISORY in found
    assert found[GLOB_ADVISORY].package == "glob"
    assert found[GLOB_ADVISORY].severity == "moderate"
    assert found.keys() >= TINYPOOL_ADVISORIES
    assert {found[i].severity for i in TINYPOOL_ADVISORIES} == {"critical"}
    assert len(found) == len({a.ident for a in audit.advisories(REAL)})


def test_an_advisory_that_reaches_several_packages_is_reported_once():
    shared = advisory(package="minimatch", ident="GHSA-1111-2222-3333")
    found = audit.advisories(report(("minimatch", [shared], [], False), ("glob", [shared, "minimatch"], [], False)))
    assert [a.ident for a in found] == ["GHSA-1111-2222-3333"]


def test_a_via_that_is_only_a_package_name_is_not_an_advisory():
    assert audit.advisories(report(("archiver", ["archiver-utils"], [], False))) == []


def test_the_direct_dependencies_that_bring_a_package_in_are_found_through_the_effects():
    vulnerable = report(
        ("glob", [advisory(package="glob")], ["archiver-utils"], False),
        ("archiver-utils", ["glob"], ["archiver"], False),
        ("archiver", ["archiver-utils"], ["nuxt"], False),
        ("nuxt", ["archiver"], [], True),
    )
    assert audit.direct_dependents(vulnerable, "glob") == ["nuxt"]


def test_in_the_real_report_the_glob_warning_comes_in_through_nuxt_and_the_coverage_plugin():
    assert audit.direct_dependents(REAL, "glob") == ["@vitest/coverage-v8", "nuxt"]


def test_a_package_that_is_itself_direct_is_its_own_route():
    assert audit.direct_dependents(report(("vitest", [advisory(package="vitest")], [], True)), "vitest") == ["vitest"]


# -- the decision ----------------------------------------------------------------------------------------------------


def test_the_real_report_fails_at_moderate_and_names_the_glob_advisory():
    result = audit.judge({"web": REAL}, level="moderate", allow=[])
    assert not result.ok
    text = "\n".join(result.failures)
    assert GLOB_ADVISORY in text
    assert "web" in text
    assert "critical" in text


def test_a_finding_below_the_level_does_not_fail_but_is_counted():
    low = report(("deepmerge", [advisory("low", "deepmerge")], [], False))
    result = audit.judge({"web": low}, level="moderate", allow=[])
    assert result.ok
    assert result.below_level == 1


def test_a_finding_at_the_level_fails():
    result = audit.judge({"web": report(("x", [advisory("moderate", "x")], [], True))}, level="moderate", allow=[])
    assert not result.ok


def test_the_level_can_be_raised_so_that_moderate_findings_pass():
    moderate = report(("x", [advisory("moderate", "x")], [], True))
    assert audit.judge({"web": moderate}, level="high", allow=[]).ok


def test_a_failure_says_what_it_is_the_route_in_and_how_to_deal_with_it():
    vulnerable = report(
        ("tinypool", [advisory("critical", "tinypool", "GHSA-5gmw-xhrv-c9v3", "RCE gadget")], ["vitest"], False),
        ("vitest", ["tinypool"], [], True),
    )
    (failure,) = audit.judge({"web": vulnerable}, level="moderate", allow=[]).failures
    assert "tinypool" in failure
    assert "critical" in failure
    assert "RCE gadget" in failure
    assert "GHSA-5gmw-xhrv-c9v3" in failure
    assert "vitest" in failure  # the direct dependency to update


def test_a_failure_whose_route_is_unknown_does_not_print_a_question_mark():
    """node-forge sits under nothing that is itself vulnerable, so npm names no direct dependency to update."""
    (failure,) = audit.judge(
        {"web": report(("node-forge", [advisory("moderate", "node-forge")], [], False))}, level="moderate", allow=[]
    ).failures
    assert "?" not in failure
    assert "override" in failure


def test_an_allowed_advisory_passes_and_its_reason_is_reported():
    vulnerable = report(("deepmerge", [advisory("moderate", "deepmerge", "GHSA-aaaa-bbbb-cccc")], [], False))
    allow = [audit.Allowed("GHSA-aaaa-bbbb-cccc", "build time only, our own config, no fix published")]
    result = audit.judge({"web": vulnerable}, level="moderate", allow=allow)
    assert result.ok
    assert result.allowed == {"GHSA-aaaa-bbbb-cccc": "build time only, our own config, no fix published"}


def test_allowing_one_advisory_does_not_hide_a_new_one_on_the_same_package():
    vulnerable = report(
        (
            "deepmerge",
            [
                advisory("moderate", "deepmerge", "GHSA-aaaa-bbbb-cccc"),
                advisory("high", "deepmerge", "GHSA-dddd-eeee-ffff"),
            ],
            [],
            False,
        )
    )
    result = audit.judge({"web": vulnerable}, level="moderate", allow=[audit.Allowed("GHSA-aaaa-bbbb-cccc", "known")])
    assert not result.ok
    assert "GHSA-dddd-eeee-ffff" in "\n".join(result.failures)
    assert "GHSA-aaaa-bbbb-cccc" not in "\n".join(result.failures)


def test_an_allow_entry_nothing_needs_any_more_fails_so_the_list_cannot_rot():
    clean = report()
    result = audit.judge(
        {"web": clean}, level="moderate", allow=[audit.Allowed("GHSA-gone-gone-gone", "was needed once")]
    )
    assert not result.ok
    assert "GHSA-gone-gone-gone" in "\n".join(result.failures)
    assert "remove" in "\n".join(result.failures)


def test_an_allow_entry_that_is_only_below_the_level_is_not_stale_but_unnecessary_and_fails_too():
    """Below the level nothing is asked of the entry, so it has no job: the list holds only what it must."""
    low = report(("deepmerge", [advisory("low", "deepmerge", "GHSA-aaaa-bbbb-cccc")], [], False))
    result = audit.judge({"web": low}, level="moderate", allow=[audit.Allowed("GHSA-aaaa-bbbb-cccc", "low")])
    assert not result.ok


def test_every_project_is_judged_and_named():
    bad = report(("x", [advisory("high", "x")], [], True))
    result = audit.judge({"web": report(), "clients/macos": bad}, level="moderate", allow=[])
    assert [f.split(":")[0] for f in result.failures] == ["clients/macos"]


# -- the allow-list in pyproject.toml ---------------------------------------------------------------------------------


def write_pyproject(tmp_path, body):
    path = tmp_path / "pyproject.toml"
    path.write_text('[project]\nname = "x"\n\n' + body, encoding="utf-8")
    return path


def test_the_allow_list_is_read_with_its_reasons(tmp_path):
    path = write_pyproject(
        tmp_path,
        '[[tool.claudia.npm-audit-allow]]\nadvisory = "GHSA-aaaa-bbbb-cccc"\nreason = "build time only"\n',
    )
    assert audit.read_allowlist(path) == [audit.Allowed("GHSA-aaaa-bbbb-cccc", "build time only")]


def test_no_allow_list_is_an_empty_one(tmp_path):
    assert audit.read_allowlist(write_pyproject(tmp_path, "")) == []


@pytest.mark.parametrize(
    "entry", ['advisory = "GHSA-aaaa-bbbb-cccc"\n', 'advisory = "GHSA-aaaa-bbbb-cccc"\nreason = "  "\n']
)
def test_an_allow_entry_without_a_written_reason_is_refused(tmp_path, entry):
    path = write_pyproject(tmp_path, "[[tool.claudia.npm-audit-allow]]\n" + entry)
    with pytest.raises(SystemExit, match="reason"):
        audit.read_allowlist(path)


def test_an_allow_entry_without_an_advisory_is_refused(tmp_path):
    path = write_pyproject(tmp_path, '[[tool.claudia.npm-audit-allow]]\nreason = "because"\n')
    with pytest.raises(SystemExit, match="advisory"):
        audit.read_allowlist(path)


def test_the_real_allow_list_in_pyproject_is_readable():
    assert isinstance(audit.read_allowlist(ROOT / "pyproject.toml"), list)


# -- asking npm ------------------------------------------------------------------------------------------------------


class Result:
    def __init__(self, stdout="", returncode=0):
        self.stdout, self.stderr, self.returncode = stdout, "", returncode


def runner(*results):
    calls = []
    queue = list(results)

    def run(command, **kwargs):
        calls.append((command, kwargs))
        item = queue.pop(0)
        if isinstance(item, Exception):
            raise item
        return item

    run.calls = calls
    return run


def test_npm_is_asked_for_the_lockfile_only_so_node_modules_is_not_needed(tmp_path):
    run = runner(Result(json.dumps(report()), returncode=0))
    assert audit.run_audit("npm", tmp_path, run=run, attempts=1) == report()
    (command, kwargs) = run.calls[0]
    assert command[1:] == ["audit", "--package-lock-only", "--json"]
    assert kwargs["cwd"] == tmp_path


def test_a_report_with_vulnerabilities_is_still_a_report_although_npm_exits_non_zero(tmp_path):
    run = runner(Result(json.dumps(REAL), returncode=1))
    assert audit.run_audit("npm", tmp_path, run=run, attempts=1) == REAL


def test_an_error_from_npm_means_the_audit_could_not_be_done(tmp_path):
    offline = {"message": "request to https://registry.npmjs.org failed", "error": {"code": "ENOTFOUND"}}
    run = runner(Result(json.dumps(offline), returncode=1))
    with pytest.raises(audit.Unreachable, match="ENOTFOUND"):
        audit.run_audit("npm", tmp_path, run=run, attempts=1)


def test_output_that_is_not_json_means_the_audit_could_not_be_done(tmp_path):
    with pytest.raises(audit.Unreachable):
        audit.run_audit("npm", tmp_path, run=runner(Result("npm ERR! something", returncode=1)), attempts=1)


def test_a_timeout_means_the_audit_could_not_be_done(tmp_path):
    with pytest.raises(audit.Unreachable, match="did not answer"):
        audit.run_audit("npm", tmp_path, run=runner(subprocess.TimeoutExpired("npm", 1)), attempts=1)


def test_a_failed_first_attempt_is_tried_once_more(tmp_path):
    """A registry that hiccups once must not turn the weekly run red."""
    run = runner(Result("", returncode=1), Result(json.dumps(report()), returncode=0))
    assert audit.run_audit("npm", tmp_path, run=run, attempts=2, pause=0) == report()
    assert len(run.calls) == 2


# -- which lockfiles ---------------------------------------------------------------------------------------------------


def test_the_lockfiles_found_are_the_web_app_and_each_client(tmp_path):
    for name in ("web", "clients/windows", "clients/macos", "clients/linux"):
        (tmp_path / name).mkdir(parents=True)
    for name in ("web", "clients/windows", "clients/macos"):
        (tmp_path / name / "package-lock.json").write_text("{}", encoding="utf-8")
    assert [str(p.relative_to(tmp_path)).replace("\\", "/") for p in audit.lockfiles(tmp_path)] == [
        "clients/macos/package-lock.json",
        "clients/windows/package-lock.json",
        "web/package-lock.json",
    ]


def test_no_package_lock_in_the_repository_escapes_the_audit():
    """A new npm project (the macOS client was one) must be audited the day it appears, not when someone remembers."""
    skip = {"node_modules", ".venv", ".git", ".mypy_cache", ".nuxt", ".output", "_build", "claudiaoffice-log"}
    found = []
    for folder, names, files in os.walk(ROOT):
        names[:] = [n for n in names if n not in skip]
        if "package-lock.json" in files:
            found.append(Path(folder) / "package-lock.json")
    assert found, "no package-lock.json found at all: the walk is wrong"
    assert set(found) <= set(audit.lockfiles(ROOT))


# -- the command -----------------------------------------------------------------------------------------------------


def test_main_passes_when_nothing_is_at_the_level(tmp_path, capsys):
    (tmp_path / "web").mkdir()
    (tmp_path / "web" / "package-lock.json").write_text("{}", encoding="utf-8")
    (tmp_path / "pyproject.toml").write_text('[project]\nname = "x"\n', encoding="utf-8")
    code = audit.main([], root=tmp_path, which=lambda name: "npm", audit=lambda npm, folder: report())
    assert code == 0
    assert "web" in capsys.readouterr().out


def test_main_fails_with_exit_1_and_prints_what_it_found(tmp_path, capsys):
    (tmp_path / "web").mkdir()
    (tmp_path / "web" / "package-lock.json").write_text("{}", encoding="utf-8")
    (tmp_path / "pyproject.toml").write_text('[project]\nname = "x"\n', encoding="utf-8")
    code = audit.main([], root=tmp_path, which=lambda name: "npm", audit=lambda npm, folder: REAL)
    assert code == 1
    assert GLOB_ADVISORY in capsys.readouterr().out


def test_main_reports_unreachable_as_its_own_exit_code_not_as_clean(tmp_path, capsys):
    (tmp_path / "web").mkdir()
    (tmp_path / "web" / "package-lock.json").write_text("{}", encoding="utf-8")
    (tmp_path / "pyproject.toml").write_text('[project]\nname = "x"\n', encoding="utf-8")

    def offline(npm, folder):
        raise audit.Unreachable("registry.npmjs.org did not answer")

    assert audit.main([], root=tmp_path, which=lambda name: "npm", audit=offline) == audit.UNREACHABLE
    assert "did not answer" in capsys.readouterr().out


def test_main_without_npm_is_unreachable_too(tmp_path, capsys):
    assert audit.main([], root=tmp_path, which=lambda name: None) == audit.UNREACHABLE
    assert "npm" in capsys.readouterr().out


def test_the_level_is_an_option():
    assert audit.parse_args([]).level == "moderate"
    assert audit.parse_args(["--level", "high"]).level == "high"


# -- in the gate -----------------------------------------------------------------------------------------------------


def test_the_audit_is_its_own_check_of_the_gate():
    (check,) = [c for c in check_debt.checks() if c.name == "npm audit"]
    assert check.command[-1].endswith("check_npm_audit.py")
    assert check.skip_returncode == audit.UNREACHABLE


def test_the_gate_skips_the_audit_where_there_is_no_npm():
    check = check_debt.npm_audit_check(which=lambda name: None)
    assert "npm" in check.skip_reason


def test_the_gate_runs_the_audit_where_npm_is_installed():
    assert check_debt.npm_audit_check(which=lambda name: "/usr/bin/npm").skip_reason == ""


def test_a_check_that_exits_with_its_skip_code_is_skipped_with_what_it_printed():
    check = check_debt.Check(
        "stand-in",
        (sys.executable, "-c", "print('the registry did not answer'); raise SystemExit(3)"),
        skip_returncode=3,
    )
    (outcome,) = check_debt.run_checks([check], fast=False)
    assert outcome.status == "skipped"
    assert "the registry did not answer" in outcome.detail


def test_any_other_non_zero_exit_of_that_check_is_still_a_failure():
    check = check_debt.Check("stand-in", (sys.executable, "-c", "raise SystemExit(1)"), skip_returncode=3)
    (outcome,) = check_debt.run_checks([check], fast=False)
    assert outcome.status == "failed"


def test_in_ci_an_unreachable_registry_fails_the_build_unless_it_is_allowed():
    skipped = [check_debt.Outcome("npm audit", "skipped", "the registry did not answer")]
    failed, _ = check_debt.verdict(skipped, ci=True, allow_skip=frozenset())
    assert failed == ["npm audit"]
