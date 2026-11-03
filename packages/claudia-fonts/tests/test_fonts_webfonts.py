"""Web fonts: WOFF2 files made from the font files by hash, and the CSS that names them (E3.3)."""

import os

import pytest
from fontTools.ttLib import TTFont

from claudia_fonts import Catalogue, Collection, CollectionRecord, NotServable, WebFontCache, font_face_css
from claudia_fonts.testing import make_font


def catalogue_of(tmp_path, *fonts, redistributable=True):
    """A catalogue of the given (file name, make_font arguments) fonts in one collection."""
    library = tmp_path / "library"
    library.mkdir(exist_ok=True)
    for file_name, kwargs in fonts:
        make_font(library / file_name, **kwargs)
    record = CollectionRecord(name="Test", licence="OFL-1.1", redistributable=redistributable)
    return Catalogue.from_collections([Collection(library, record)])


def url_for(font):
    return f"/fonts/{font.sha256}.woff2"


# -- the files ------------------------------------------------------------------------------------------------------


def test_a_woff2_file_is_made_and_named_by_the_hash_of_the_font(tmp_path):
    [font] = catalogue_of(tmp_path, ("a.ttf", {"family": "Alpha"})).fonts()
    path = WebFontCache(tmp_path / "cache").get(font)
    assert path == tmp_path / "cache" / f"{font.sha256}.woff2"
    assert TTFont(path).flavor == "woff2"


def test_the_cache_folder_is_made_when_it_is_missing(tmp_path):
    [font] = catalogue_of(tmp_path, ("a.ttf", {"family": "Alpha"})).fonts()
    WebFontCache(tmp_path / "deep" / "cache").get(font)
    assert (tmp_path / "deep" / "cache").is_dir()


def test_a_font_that_is_already_converted_is_not_converted_again(tmp_path):
    [font] = catalogue_of(tmp_path, ("a.ttf", {"family": "Alpha"})).fonts()
    cache = WebFontCache(tmp_path / "cache")
    path = cache.get(font)
    os.utime(path, ns=(1, 1))
    assert cache.get(font) == path
    assert path.stat().st_mtime_ns == 1


def test_a_new_cache_object_finds_what_an_older_one_made(tmp_path):
    [font] = catalogue_of(tmp_path, ("a.ttf", {"family": "Alpha"})).fonts()
    path = WebFontCache(tmp_path / "cache").get(font)
    os.utime(path, ns=(1, 1))
    WebFontCache(tmp_path / "cache").get(font)
    assert path.stat().st_mtime_ns == 1


def test_no_half_written_file_is_left_behind(tmp_path):
    [font] = catalogue_of(tmp_path, ("a.ttf", {"family": "Alpha"})).fonts()
    WebFontCache(tmp_path / "cache").get(font)
    assert [p.suffix for p in (tmp_path / "cache").iterdir()] == [".woff2"]


def test_a_font_that_changed_on_disk_since_the_catalogue_was_made_is_not_served_under_the_old_hash(tmp_path):
    catalogue = catalogue_of(tmp_path, ("a.ttf", {"family": "Alpha", "version": "1.0"}))
    [font] = catalogue.fonts()
    make_font(font.path, "Alpha", version="9.9")
    with pytest.raises(NotServable, match="changed"):
        WebFontCache(tmp_path / "cache").get(font)
    assert not (tmp_path / "cache").exists() or list((tmp_path / "cache").iterdir()) == []


def test_a_font_that_may_not_be_handed_out_is_not_served(tmp_path):
    [font] = catalogue_of(tmp_path, ("a.ttf", {"family": "Alpha"}), redistributable=False).fonts()
    with pytest.raises(NotServable, match="Alpha"):
        WebFontCache(tmp_path / "cache").get(font)


# -- the CSS --------------------------------------------------------------------------------------------------------


def test_the_css_has_one_rule_per_style_with_weight_slant_and_the_hashed_address(tmp_path):
    catalogue = catalogue_of(
        tmp_path,
        ("r.ttf", {"family": "Alpha", "style": "Regular"}),
        ("b.ttf", {"family": "Alpha", "style": "Bold Italic", "weight": 700, "italic": True}),
    )
    regular, bold = catalogue.fonts_of("Alpha")
    css = font_face_css(catalogue, "Alpha", url_for)
    assert css.count("@font-face") == 2
    assert 'font-family: "Alpha";' in css
    assert "font-weight: 700;" in css
    assert "font-style: italic;" in css
    assert "font-style: normal;" in css
    assert "font-display: swap;" in css
    assert f'src: url("/fonts/{regular.sha256}.woff2") format("woff2");' in css
    assert f'src: url("/fonts/{bold.sha256}.woff2") format("woff2");' in css


def test_the_caller_chooses_the_addresses(tmp_path):
    catalogue = catalogue_of(tmp_path, ("a.ttf", {"family": "Alpha"}))
    css = font_face_css(catalogue, "Alpha", lambda font: f"https://example.org/{font.sha256[:8]}")
    assert 'url("https://example.org/' in css


def test_the_family_is_found_whatever_its_case(tmp_path):
    catalogue = catalogue_of(tmp_path, ("a.ttf", {"family": "Alpha"}))
    assert 'font-family: "Alpha";' in font_face_css(catalogue, "alpha", url_for)


def test_quotes_and_backslashes_in_a_family_name_are_escaped_so_they_cannot_end_the_string(tmp_path):
    name = 'Odd"x\\'  # Odd, a quote, x, a backslash
    catalogue = catalogue_of(tmp_path, ("a.ttf", {"family": name}))
    css = font_face_css(catalogue, name, url_for)
    assert 'font-family: "Odd\\"x\\\\";' in css
    assert css.count("{") == 1
    assert css.count("}") == 1


def test_a_family_nobody_may_be_given_has_no_rules(tmp_path):
    catalogue = catalogue_of(tmp_path, ("a.ttf", {"family": "Alpha"}), redistributable=False)
    assert font_face_css(catalogue, "Alpha", url_for) == ""


def test_an_unknown_family_is_an_error(tmp_path):
    catalogue = catalogue_of(tmp_path, ("a.ttf", {"family": "Alpha"}))
    with pytest.raises(KeyError):
        font_face_css(catalogue, "Missing", url_for)
