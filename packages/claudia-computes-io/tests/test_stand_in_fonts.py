"""The shared sample of the font stand-ins (``test-documents/xlsx/stand-in-fonts``, E3.13) through ods as well: each
cell keeps the name of its font and its generic family, and no stand-in is written into either file format."""

import json
from pathlib import Path

from claudia_computes_io import ods_to_workbook, workbook_to_ods, xlsx_to_workbook

from claudia_computes import SheetId
from claudia_opc_io import read_parts

SAMPLE = Path(__file__).resolve().parents[3] / "test-documents" / "xlsx" / "stand-in-fonts"
FONTS = json.loads((SAMPLE / "stand-ins.json").read_text(encoding="utf-8"))["fonts"]


def stacks(model) -> list[str]:
    sheet = model.sheets[SheetId("s1")]
    return [
        model.styles.get(sheet.cell_styles.style_at(row, 0, "words")[0]).css["font-family"] for row in range(len(FONTS))
    ]


def test_the_sample_keeps_every_font_name_through_ods():
    model = xlsx_to_workbook((SAMPLE / "source.xlsx").read_bytes())
    ods = workbook_to_ods(model)
    assert stacks(ods_to_workbook(ods)) == stacks(model)
    written = read_parts(ods)["styles.xml"].decode() + read_parts(ods)["content.xml"].decode()
    for entry in FONTS:
        assert entry["family"] in written, entry["family"]
    for stand_in in {e["stand_in"] for e in FONTS} - {e["family"] for e in FONTS} - {None}:
        assert stand_in not in written, f"{stand_in} is a stand-in, never written into the file"
