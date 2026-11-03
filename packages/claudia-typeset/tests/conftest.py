"""Fixtures shared by the typesetting tests: a small font catalogue, and the real TeX fonts when TeX is installed."""

import shutil
import subprocess
from pathlib import Path

import pytest

from claudia_fonts import Catalogue, Collection, CollectionRecord
from claudia_fonts.testing import make_font

TEX_PROGRAMS = ("xelatex", "pdftocairo", "kpsewhich")


@pytest.fixture
def needs_tex():
    """Skips the test where TeX is not installed (the engine tests then run in CI, where it is)."""
    missing = [program for program in TEX_PROGRAMS if not shutil.which(program)]
    if missing:
        pytest.skip(f"not installed: {', '.join(missing)}")


@pytest.fixture
def catalogue(tmp_path):
    folder = tmp_path / "tex"
    folder.mkdir()
    make_font(folder / "lm.ttf", "Latin Modern Roman")
    make_font(folder / "lmmath.ttf", "Latin Modern Math", math=True)
    make_font(folder / "lib.ttf", "Liberation Serif")
    record = CollectionRecord(name="test", licence="test licence", redistributable=True)
    return Catalogue.from_collections([Collection(folder, record)])


@pytest.fixture
def tex_catalogue(tmp_path, needs_tex):
    """The Latin Modern fonts of the installed TeX Live, as a collection of their own (links, so nothing is copied)."""
    folder = tmp_path / "tex-fonts"
    folder.mkdir()
    for name in ("latinmodern-math.otf", "lmroman10-regular.otf", "lmroman10-bold.otf", "lmroman10-italic.otf"):
        found = subprocess.run(["kpsewhich", name], capture_output=True, text=True, check=False).stdout.strip()
        if not found:
            pytest.skip(f"TeX Live has no {name}")
        (folder / name).symlink_to(Path(found))
    record = CollectionRecord(name="tex-live", licence="GUST Font License", redistributable=True)
    return Catalogue.from_collections([Collection(folder, record)])
