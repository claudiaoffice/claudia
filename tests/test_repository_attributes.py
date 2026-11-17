"""Files whose bytes are pinned by a hash come out of a checkout exactly as they went in, on every system."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
#: The starter fonts and their licence texts: ``starter.lock.json`` pins each file by its SHA-256.
PINNED = "packages/claudia-fonts/src/claudia_fonts/builtin"


def _attribute(name: str, path: str) -> str:
    done = subprocess.run(
        ["git", "check-attr", name, "--", path], cwd=ROOT, capture_output=True, text=True, check=False
    )
    if done.returncode != 0:
        pytest.skip("not a Git checkout")
    return done.stdout.strip().rsplit(": ", 1)[-1]


@pytest.mark.skipif(shutil.which("git") is None, reason="needs git")
@pytest.mark.parametrize("file", ["arimo/OFL.txt", "carlito/OFL.txt", "inter/OFL.txt"])
def test_git_never_converts_the_line_endings_of_a_pinned_font_file(file):
    """On Windows a checkout turns the line feeds of a text file into carriage returns and line feeds, which changes
    the hash that the package's lock pins (the font tests failed on Windows only)."""
    assert _attribute("text", f"{PINNED}/{file}") == "unset"
