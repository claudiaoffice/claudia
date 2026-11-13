"""The files ``scripts/odf_libreoffice_check.py`` hands to LibreOffice can still be made, without LibreOffice (PROC-11).

The script runs only in its own CI job, which may fail without failing the build (D409). So when the styling suite made
a shape's outline and its words two slots (D310, D316), the script's hand-built deck -- a shape whose words were put
under the outline style -- broke there and nowhere else, and nobody saw it until the job was read. Building the three
new files is plain Python and needs no ``soffice``: it belongs in the suite that always runs.
"""

import importlib.util
import sys
from pathlib import Path

SPEC = importlib.util.spec_from_file_location(
    "odf_libreoffice_check", Path(__file__).parent.parent / "scripts" / "odf_libreoffice_check.py"
)
check = importlib.util.module_from_spec(SPEC)
sys.modules["odf_libreoffice_check"] = check
SPEC.loader.exec_module(check)


def test_the_new_text_is_made_and_reads_back_with_every_block():
    data, shown = check.new_file()
    assert data.startswith(b"PK")
    assert shown[0] == "Annual report"
    assert "Words of someone else" in shown


def test_the_new_deck_is_made_with_the_styles_the_server_gives_new_objects():
    data, shown = check.new_deck()
    assert data.startswith(b"PK")
    assert shown == ["Annual report\nSecond line & <more>", "boxed", "tri"]


def test_the_new_workbook_is_made_and_reads_back_as_a_workbook():
    data, workbook = check.new_workbook()
    assert data.startswith(b"PK")
    assert [sheet.name for sheet in workbook.sheets.values()] == ["Data", "Notes"]


def test_every_library_case_can_be_edited_the_way_its_spec_says():
    cases = check.library_cases()
    assert cases, "the test-document library has odt, odp and ods entries"
    for name, fmt, source, edited, _ in cases:
        assert fmt in ("odt", "odp", "ods"), name
        assert source and edited, name
