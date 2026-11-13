"""The server runs on one Python version, named in ``.python-version``, and everything that picks one agrees (PROC-13).

``requires-python = ">=3.14"`` alone lets ``uv`` take the newest interpreter it can find. Once Python 3.15 was on a
machine, ``uv sync`` made the environment with it -- and OpenVINO GenAI, the language model of ``--ai``, publishes
wheels for 3.14 only (``uv.lock`` has no 3.15 wheel and no sdist), so the AI could not be installed until 3.14 was
forced by hand. ``.python-version`` is what ``uv`` reads to choose; this keeps it, CI, the image and the Debian package
on the same version, so moving to 3.15 is one deliberate change in every place at once, not something a laptop does
by itself.
"""

import re
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def pinned() -> str:
    return (ROOT / ".python-version").read_text(encoding="utf-8").strip()


def test_the_repository_names_one_python_version():
    assert re.fullmatch(r"3\.\d+", pinned()), "a minor version: uv takes its newest patch release"


def test_the_pinned_version_is_the_floor_of_every_server_package():
    floors = {f">={pinned()}"}
    for pyproject in [ROOT / "pyproject.toml", *sorted((ROOT / "packages").glob("*/pyproject.toml"))]:
        requires = tomllib.loads(pyproject.read_text(encoding="utf-8"))["project"]["requires-python"]
        assert requires in floors, f"{pyproject.relative_to(ROOT)}: requires-python {requires!r}"


def test_ci_sets_up_the_pinned_version_everywhere():
    for workflow in sorted((ROOT / ".github" / "workflows").glob("*.yml")):
        for found in re.findall(r'python-version:\s*"([^"]+)"', workflow.read_text(encoding="utf-8")):
            assert found == pinned(), f"{workflow.name} sets up Python {found}"


def test_the_image_and_the_debian_package_build_on_the_pinned_version():
    bases = re.findall(r"^FROM python:(\d+\.\d+)", (ROOT / "Dockerfile").read_text(encoding="utf-8"), re.MULTILINE)
    assert bases and set(bases) == {pinned()}
    deb = (ROOT / "packaging" / "debian" / "build-deb.sh").read_text(encoding="utf-8")
    assert set(re.findall(r"python(?: install)? (\d+\.\d+)", deb)) == {pinned()}
