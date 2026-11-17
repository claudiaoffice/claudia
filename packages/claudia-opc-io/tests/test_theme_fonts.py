"""The fonts of an Office theme (E3.13): the heading and body fonts, and what a reference to one names."""

from claudia_opc_io import ThemeFonts

THEME = b"""<?xml version="1.0"?><a:theme xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main"><a:themeElements>
<a:fontScheme name="x"><a:majorFont><a:latin typeface="Georgia"/><a:ea typeface=""/></a:majorFont>
<a:minorFont><a:latin typeface="Arial"/></a:minorFont></a:fontScheme></a:themeElements></a:theme>"""


def test_a_theme_says_its_heading_and_body_fonts():
    fonts = ThemeFonts.read(THEME)
    assert (fonts.major, fonts.minor) == ("Georgia", "Arial")


def test_a_reference_to_a_theme_font_is_the_font_it_names_in_both_notations():
    fonts = ThemeFonts.read(THEME)
    assert [fonts.named(ref) for ref in ("+mj-lt", "+mn-lt", "majorHAnsi", "minorAscii", "Calibri")] == [
        "Georgia",
        "Arial",
        "Georgia",
        "Arial",
        "Calibri",
    ]
    assert fonts.named("+mn-ea") is None and fonts.named("") is None


def test_no_theme_or_an_empty_one_names_nothing():
    assert ThemeFonts.read(None) == ThemeFonts(None, None)
    assert ThemeFonts.read(b"<a:theme xmlns:a='http://schemas.openxmlformats.org/drawingml/2006/main'/>").minor is None
