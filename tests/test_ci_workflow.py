"""CI runs what the repository says it can run (PROC-19).

At ``cfa2d91`` six of the eighteen browser scripts in ``web/package.json`` (lists, regions, the grid's accessibility,
describing objects in computes and creates, the macOS shell window) were never run by CI, and the macOS client's own
tests, type check and build ran nowhere at all. Two of them rotted the same way the scripts did before PROC-06. These
checks read the workflow as text: a script or a client that is not mentioned there is not run.
"""

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CI = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")


def _e2e_scripts() -> list[str]:
    scripts = json.loads((ROOT / "web" / "package.json").read_text(encoding="utf-8"))["scripts"]
    return sorted(name for name in scripts if name == "e2e" or name.startswith("e2e:"))


def test_every_browser_script_of_the_web_app_is_run_by_ci():
    run = set(re.findall(r"npm run (e2e(?::[\w-]+)?)\b", CI))
    missing = [name for name in _e2e_scripts() if name not in run]
    assert not missing, f"web/package.json has browser scripts CI never runs: {missing}"


def test_every_native_client_with_its_own_tests_is_tested_by_ci():
    package = json.loads((ROOT / "clients" / "neutralino" / "package.json").read_text(encoding="utf-8"))
    assert "test" in package["scripts"]
    # a job that installs the client's own dependencies is one that can run its tests
    assert "cache-dependency-path: clients/neutralino/package-lock.json" in CI, "no CI job tests clients/neutralino"


def test_the_neutralino_client_is_built_for_both_systems_by_ci():
    """One package for macOS and Windows (D660): a bundle is made for one system, so CI makes both."""
    for system in ("macos", "windows"):
        assert f"npm run build:{system}" in CI, f"CI never builds clients/neutralino for {system}"


def test_the_image_and_package_builds_notice_a_change_to_the_layout_library():
    """The web app links the layout library (D902); a change there changes the image and the .deb."""
    for workflow in ("docker.yml", "deb.yml"):
        text = (ROOT / ".github" / "workflows" / workflow).read_text(encoding="utf-8")
        assert "- layout/**" in text, f"{workflow} does not run for a change in layout/"


def test_the_demo_is_deployed_only_after_ci_has_passed_on_the_commit():
    """The image is built by its own workflow, in parallel with CI, so "the image was built" says nothing about the
    tests: at f150f0d main was red and the demo would still have been replaced. The deployment starts when CI has
    succeeded on a push to main, and then waits for the image of that commit."""
    deploy = (ROOT / ".github" / "workflows" / "deploy-demo.yml").read_text(encoding="utf-8")
    trigger = re.search(r"workflow_run:\s*\n\s*workflows: \[(.*?)\]", deploy)
    assert trigger, "deploy-demo.yml is not started by a workflow_run"
    assert trigger[1].strip() == '"CI"', f"the demo is deployed after {trigger[1]}, not after CI"
    assert "workflow_run.event == 'push'" in deploy and "workflow_run.head_branch == 'main'" in deploy
    copy = deploy.split("Copy the image from GHCR", 1)[1].split("- name: Deploy", 1)[0]
    assert "docker pull" in copy and "for _ in" in copy, (
        "the image of the commit may still be building when CI ends: the copy must wait for it"
    )


def test_every_lockfile_is_watched_by_dependabot():
    """A lockfile nobody updates is a known hole waiting (SEC-08): each npm lockfile and the uv lock has an entry."""
    watched = (ROOT / ".github" / "dependabot.yml").read_text(encoding="utf-8")
    directories = set(re.findall(r"directory: (\S+)", watched))
    lockfiles = [
        path.parent.relative_to(ROOT).as_posix()
        for path in ROOT.rglob("package-lock.json")
        if "node_modules" not in path.parts
    ]
    missing = sorted(f"/{folder}" for folder in lockfiles if f"/{folder}" not in directories)
    assert not missing, f"dependabot.yml does not watch: {missing}"
    assert "package-ecosystem: uv" in watched and "package-ecosystem: github-actions" in watched


# -- PROC-27: the supply chain of CI ------------------------------------------------------------------------------
WORKFLOWS = sorted((ROOT / ".github" / "workflows").glob("*.yml"))
_USES = re.compile(r"^\s*-?\s*uses:\s*(?P<action>\S+)(?P<rest>.*)$", re.MULTILINE)


def test_every_action_of_somebody_else_is_pinned_to_a_commit():
    """A tag moves: whoever controls an action's repository can change what ``@v5`` runs in our workflows, with our
    secrets in reach. A commit does not move. The comment names the version, which is what dependabot reads to propose
    the next pin (``.github/dependabot.yml`` watches the actions)."""
    loose = []
    for workflow in WORKFLOWS:
        for found in _USES.finditer(workflow.read_text(encoding="utf-8")):
            action = found["action"]
            if action.startswith("./"):
                continue
            pinned = re.fullmatch(r"[\w.-]+/[\w./-]+@[0-9a-f]{40}", action)
            versioned = re.match(r"\s*#\s*v\d", found["rest"])
            if not (pinned and versioned):
                loose.append(f"{workflow.name}: {action}{found['rest']}")
    assert not loose, "pin by commit, with the version as a comment (`@<sha> # v5.1.0`):\n" + "\n".join(loose)


def test_the_image_workflow_does_not_publish_the_tags_that_mean_a_good_main():
    """``latest`` and ``main`` are what people pull to get the current version. The image workflow runs beside CI, so
    at f150f0d a red main would still have become ``latest``. It pushes ``sha-…`` (the demo deploys that, after CI) and
    the release tags; promoting ``latest`` and ``main`` is the promotion workflow's job, after CI."""
    docker = (ROOT / ".github" / "workflows" / "docker.yml").read_text(encoding="utf-8")
    tags = docker.split("id: meta", 1)[1].split("labels:", 1)[0]
    assert "value=latest" not in tags and "event=branch" not in tags
    assert "type=sha" in tags and "type=semver" in tags


def test_latest_and_main_are_promoted_only_after_ci_has_passed_on_the_commit():
    promote = (ROOT / ".github" / "workflows" / "promote-image.yml").read_text(encoding="utf-8")
    trigger = re.search(r"workflow_run:\s*\n\s*workflows: \[(.*?)\]", promote)
    assert trigger and trigger[1].strip() == '"CI"'
    assert "workflow_run.conclusion == 'success'" in promote
    assert "workflow_run.event == 'push'" in promote and "workflow_run.head_branch == 'main'" in promote
    assert "imagetools create" in promote and ":latest" in promote and ":main" in promote
    assert "for _ in" in promote, "the image of the commit may still be building when CI ends: wait for it"
    assert "packages: write" in promote


def test_codeql_looks_at_python_and_javascript_every_week_and_on_every_change():
    codeql = (ROOT / ".github" / "workflows" / "codeql.yml").read_text(encoding="utf-8")
    assert "security-events: write" in codeql
    assert "python" in codeql and "javascript-typescript" in codeql
    for trigger in ("push:", "pull_request:", "schedule:"):
        assert trigger in codeql


def test_ci_audits_the_locked_python_dependencies():
    """SEC-08: ``npm audit`` ran in the gate; the Python side was audited by hand once in a while."""
    assert re.search(r"pip-audit .*-r \S+", CI), "ci.yml never runs pip-audit on the locked requirements"
    assert "uv export --frozen" in CI
