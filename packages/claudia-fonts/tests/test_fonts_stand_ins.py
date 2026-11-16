"""Stand-ins (E3.13): what a server with only the shipped fonts shows each font of the shared sample with, and the
one table that says it (:mod:`claudia_core.stand_ins`)."""

import json
from pathlib import Path

import pytest

from claudia_fonts import (
    CLOSENESS,
    COLLECTION_FILE,
    DEFAULT_GENERICS,
    DEFAULT_SUBSTITUTIONS,
    Catalogue,
    Resolution,
    builtin_folder,
    collection_folders,
)
from claudia_fonts.testing import make_font

SAMPLE = Path(__file__).resolve().parents[3] / "test-documents" / "stand-in-fonts.json"
EXPECTED = json.loads(SAMPLE.read_text(encoding="utf-8"))["fonts"]


@pytest.fixture(scope="module")
def shipped() -> Catalogue:
    return Catalogue.from_folders(collection_folders(builtin_folder()))


@pytest.mark.parametrize("entry", EXPECTED, ids=lambda e: e["family"])
def test_the_shipped_fonts_give_each_font_of_the_sample_its_stand_in(shipped, entry):
    got = shipped.resolve(entry["family"])
    assert (got.provided, got.closeness) == (entry["stand_in"], entry["closeness"])


def test_closeness_has_three_words_and_a_resolution_says_one():
    assert CLOSENESS == ("same", "same-widths", "other")
    assert Resolution("Inter", "Inter", substituted=False).closeness == "same"
    assert Resolution("Arial", "Arimo", substituted=True).closeness == "same-widths"
    assert Resolution("Century Gothic", None, substituted=False).closeness == "other"


def test_every_stand_in_and_every_generic_family_is_shipped(shipped):
    """A table entry whose font is not shipped would quietly do nothing on a server without the network."""
    assert set(DEFAULT_SUBSTITUTIONS.values()) <= set(shipped.families())
    assert set(DEFAULT_GENERICS.values()) <= set(shipped.families())
    assert set(DEFAULT_GENERICS) == {"serif", "sans-serif", "monospace", "fallback"}


def test_a_font_the_server_has_is_never_stood_in_for(tmp_path):
    """An operator who adds Arial gets Arial: the table only answers for fonts that are missing."""
    added = tmp_path / "arial"
    added.mkdir()
    (added / COLLECTION_FILE).write_text(
        json.dumps({"format": 1, "name": "Arial", "licence": "test", "redistributable": False}), encoding="utf-8"
    )
    make_font(added / "Arial.ttf", "Arial")
    catalogue = Catalogue.from_folders([*collection_folders(builtin_folder()), added])
    assert (catalogue.resolve("Arial").provided, catalogue.resolve("Arial").closeness) == ("Arial", "same")
    assert catalogue.resolve("Helvetica").provided == "Arimo"
