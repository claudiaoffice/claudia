"""Reading one font file: what it is called, how it looks, what it may be used for (E3.3)."""

import hashlib
import sys

import pytest

from claudia_fonts import Collection, CollectionRecord, FontProblem, read_font
from claudia_fonts.testing import make_font

RECORD = CollectionRecord(name="Test", licence="OFL-1.1", redistributable=True)


def read(path, record=RECORD):
    return read_font(path, Collection(path.parent, record))


def test_a_font_is_described_by_family_style_weight_and_slant(tmp_path):
    font = read(make_font(tmp_path / "a.ttf", "Test Sans", "Bold Italic", weight=700, italic=True))
    assert (font.family, font.style, font.weight, font.italic) == ("Test Sans", "Bold Italic", 700, True)


def test_an_upright_font_is_not_italic(tmp_path):
    assert read(make_font(tmp_path / "a.ttf")).italic is False


def test_typographic_names_win_over_the_legacy_family(tmp_path):
    font = read(make_font(tmp_path / "l.ttf", "Test Sans", "Light", weight=300, typographic=True))
    assert (font.family, font.style) == ("Test Sans", "Light")


def test_the_hash_is_the_sha256_of_the_bytes(tmp_path):
    path = make_font(tmp_path / "a.ttf")
    assert read(path).sha256 == hashlib.sha256(path.read_bytes()).hexdigest()


def test_other_bytes_make_another_hash(tmp_path):
    first = read(make_font(tmp_path / "a.ttf", version="1.0"))
    second = read(make_font(tmp_path / "b.ttf", version="1.1"))
    assert first.sha256 != second.sha256


def test_the_collection_decides_licence_and_whether_the_font_may_be_handed_out(tmp_path):
    record = CollectionRecord(name="Closed", licence="Proprietary", redistributable=False)
    font = read(make_font(tmp_path / "a.ttf"), record)
    assert (font.collection, font.licence, font.redistributable) == ("Closed", "Proprietary", False)


def test_a_math_font_is_flagged_and_an_ordinary_one_is_not(tmp_path):
    assert read(make_font(tmp_path / "m.ttf", math=True)).math is True
    assert read(make_font(tmp_path / "t.ttf")).math is False


def test_a_font_that_forbids_embedding_is_refused(tmp_path):
    path = make_font(tmp_path / "r.ttf", fs_type=0x0002)
    with pytest.raises(FontProblem, match="embedding"):
        read(path)


def test_preview_and_editable_bits_alone_do_not_restrict(tmp_path):
    """Latin Modern says 12 (preview and print, editable): it is free to embed, and must not be refused."""
    assert read(make_font(tmp_path / "lm.ttf", fs_type=0x000C)).family == "Test Sans"


def test_a_file_that_is_not_a_font_is_refused(tmp_path):
    path = tmp_path / "x.ttf"
    path.write_text("this is not a font", encoding="utf-8")
    with pytest.raises(FontProblem, match="not a font"):
        read(path)


@pytest.mark.skipif(sys.platform == "win32", reason="Windows does not allow these characters in file names")
@pytest.mark.parametrize("name", ["we*ird.ttf", "what?.ttf"])
def test_wildcards_in_a_file_name_are_refused(tmp_path, name):
    """The engine setup hides files by name pattern; a name with a wildcard could not be hidden exactly."""
    path = make_font(tmp_path / name)
    with pytest.raises(FontProblem, match="wildcard"):
        read(path)


def test_a_font_can_be_listed_as_plain_data(tmp_path):
    font = read(make_font(tmp_path / "a.ttf", "Test Sans", "Bold", weight=700))
    assert font.to_data() == {
        "family": "Test Sans",
        "style": "Bold",
        "weight": 700,
        "italic": False,
        "sha256": font.sha256,
        "collection": "Test",
        "licence": "OFL-1.1",
        "redistributable": True,
        "math": False,
        "axes": [],
        "outlines": "truetype",
    }


def test_a_static_font_has_no_axes_and_truetype_outlines(tmp_path):
    font = read(make_font(tmp_path / "s.ttf"))
    assert (font.axes, font.outlines) == ((), "truetype")
    assert font.to_data()["axes"] == [] and font.to_data()["outlines"] == "truetype"


def test_a_variable_font_lists_its_axes_for_clients(tmp_path):
    font = read(make_font(tmp_path / "v.ttf", axes=(("wght", 100, 400, 900), ("opsz", 14, 14, 32))))
    assert [a.tag for a in font.axes] == ["wght", "opsz"]
    assert font.to_data()["axes"][0] == {"tag": "wght", "min": 100.0, "default": 400.0, "max": 900.0}
