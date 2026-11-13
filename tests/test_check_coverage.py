"""The coverage floors (CODE-01): each package may not fall below its floor, and a floor only ever goes up.

``compare`` and ``ratcheted`` are the pure decisions of ``scripts/check_coverage.py``; ``measure`` is checked once
against a real, tiny coverage data file made here, so these tests never depend on what the last suite run left behind.
"""

import importlib.util
import os
import subprocess
import sys
from pathlib import Path

import pytest

SPEC = importlib.util.spec_from_file_location(
    "check_coverage", Path(__file__).parent.parent / "scripts" / "check_coverage.py"
)
check_coverage = importlib.util.module_from_spec(SPEC)
sys.modules["check_coverage"] = check_coverage
SPEC.loader.exec_module(check_coverage)


def test_a_package_at_or_above_its_floor_passes():
    report = check_coverage.compare({"claudia-core": 93.8, "claudia-ai": 99.0}, {"claudia-core": 93, "claudia-ai": 99})
    assert report.failures == []


def test_a_package_below_its_floor_fails_and_says_by_how_much():
    report = check_coverage.compare({"claudia-core": 91.5}, {"claudia-core": 93})
    assert report.failures == ["claudia-core: 91.5% is below its floor of 93%"]


def test_a_package_without_a_floor_fails_until_it_gets_one():
    """A new package starts at its measured value (``--ratchet`` writes it), never at no floor at all."""
    report = check_coverage.compare({"claudia-new": 80.0}, {})
    assert report.failures == ["claudia-new: 80.0% has no floor yet (run with --ratchet to set it)"]


def test_a_floor_for_a_package_that_was_not_measured_fails():
    """A renamed or removed package, or a run that did not measure it: either way the floor is not being held."""
    report = check_coverage.compare({}, {"claudia-gone": 90})
    assert report.failures == ["claudia-gone: has a floor of 90% but was not measured"]


def test_a_floor_that_could_go_up_is_named_but_does_not_fail():
    report = check_coverage.compare({"claudia-core": 95.2}, {"claudia-core": 93})
    assert report.failures == []
    assert report.raisable == {"claudia-core": 95}


def test_ratcheting_raises_and_adds_floors_and_never_lowers_one():
    floors = {"claudia-core": 93, "claudia-ai": 99}
    measured = {"claudia-core": 95.2, "claudia-ai": 97.0, "claudia-new": 80.4}
    assert check_coverage.ratcheted(floors, measured) == {"claudia-core": 95, "claudia-ai": 99, "claudia-new": 80}


def test_floors_are_read_from_and_written_back_to_pyproject(tmp_path):
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text(
        '[project]\nname = "x"\n\n'
        "[tool.claudia.coverage-floors]\n"
        "# what the suite reached on 2026-11-10\n"
        '"claudia-core" = 93\n"claudia-ai" = 99\n\n'
        "[tool.ruff]\nline-length = 120\n"
    )
    assert check_coverage.read_floors(pyproject) == {"claudia-core": 93, "claudia-ai": 99}
    check_coverage.write_floors(pyproject, {"claudia-core": 95, "claudia-ai": 99, "claudia-new": 80})
    assert check_coverage.read_floors(pyproject) == {"claudia-core": 95, "claudia-ai": 99, "claudia-new": 80}
    text = pyproject.read_text()
    assert "# what the suite reached on 2026-11-10" in text, "the table's own comment survives a rewrite"
    assert text.endswith("[tool.ruff]\nline-length = 120\n"), "nothing after the table is touched"


def test_measure_gives_each_package_its_own_percentage(tmp_path):
    """Two packages, one function each run and one not, read back from a real data file.

    The data is made by a coverage run in a process of its own: starting a second measurement inside this one would
    stop the suite's own (``--cov``), and every test after this one would go unmeasured."""
    for name in ("claudia-a", "claudia-b"):
        source = tmp_path / "packages" / name / "src" / name.replace("-", "_")
        source.mkdir(parents=True)
        (source / "__init__.py").write_text("def used():\n    return 1\n\n\ndef unused():\n    return 2\n")
    (tmp_path / "run.py").write_text("import claudia_a, claudia_b\n\nclaudia_a.used()\nclaudia_b.used()\n")
    (tmp_path / "empty.toml").write_text("")
    data = tmp_path / ".coverage"
    paths = os.pathsep.join(str(tmp_path / "packages" / name / "src") for name in ("claudia-a", "claudia-b"))
    subprocess.run(
        [
            sys.executable,
            "-m",
            "coverage",
            "run",
            f"--data-file={data}",
            f"--source={tmp_path / 'packages'}",
            f"--rcfile={tmp_path / 'empty.toml'}",
            "run.py",
        ],
        cwd=tmp_path,
        env={**os.environ, "PYTHONPATH": paths},
        check=True,
    )
    measured = check_coverage.measure(data, tmp_path / "packages")
    assert measured.keys() == {"claudia-a", "claudia-b"}
    # four statements each, three run (the two `def`s and `return 1`)
    assert measured["claudia-a"] == pytest.approx(75.0)
    assert measured["claudia-b"] == pytest.approx(75.0)


def test_measuring_without_data_says_how_to_make_it(tmp_path):
    with pytest.raises(SystemExit, match="--cov"):
        check_coverage.measure(tmp_path / ".coverage", tmp_path)
