"""The fonts of an ODF file (E3.13): font faces by name, and the font a style's text properties name."""

from lxml import etree

from claudia_odf_io import NS, font_faces, font_of

DECLS = " ".join(f'xmlns:{p}="{u}"' for p, u in NS.items() if p != "xml")
ROOT = etree.fromstring(
    f"<office:document-styles {DECLS}><office:font-face-decls>"
    '<style:font-face style:name="Liberation Sans1" svg:font-family="\'Liberation Sans\'"/>'
    '<style:font-face style:name="Arial" svg:font-family="Arial"/></office:font-face-decls></office:document-styles>'
)


def props(attributes: str) -> etree._Element:
    return etree.fromstring(f"<style:text-properties {DECLS} {attributes}/>")


def test_a_font_face_is_found_by_its_name_and_says_its_family_unquoted():
    assert font_faces(ROOT) == {"Liberation Sans1": "Liberation Sans", "Arial": "Arial"}


def test_text_properties_name_a_font_by_its_face_or_by_family():
    faces = font_faces(ROOT)
    assert font_of(props('style:font-name="Liberation Sans1"'), faces) == "Liberation Sans"
    assert font_of(props("fo:font-family=\"'Century Gothic', sans-serif\""), faces) == "Century Gothic"
    assert font_of(props('style:font-name="Unknown"'), faces) == "Unknown"
    assert font_of(props('fo:font-size="12pt"'), faces) is None
