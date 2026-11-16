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
