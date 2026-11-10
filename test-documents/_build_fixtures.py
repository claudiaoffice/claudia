"""Regenerates every checked-in ``source.docx``/``source.pptx``/``source.xlsx`` in this library, deterministically
(D218, D219, D220).

A test document is checked in as a real, openable binary -- not just a Python function that builds one on the
fly, the way every other format test in this repo does -- because the whole point of a *library* is files a
person (or LibreOffice, or real Word/PowerPoint) can open directly, not just assertions about one. This script is
how they were made, and how to remake or extend them: nobody hand-edits a ``source.docx``/``source.pptx``.

``uv run python test-documents/_build_fixtures.py``
"""

from __future__ import annotations

from io import BytesIO
from pathlib import Path

import docx
import openpyxl
import pptx
from docx.shared import Inches
from openpyxl.chart import BarChart, Reference
from openpyxl.drawing.image import Image as XLImage
from PIL import Image
from pptx.enum.shapes import MSO_SHAPE
from pptx.util import Emu

ROOT = Path(__file__).resolve().parent
#: EMU per claudia slide unit on a 16:9 deck (``12_192_000 / 1600`` == ``6_858_000 / 900``, both exact) -- the
#: same scale ``claudia_creates_io.pptx`` itself uses, so a shape placed at claudia unit ``(x, y, w, h)`` here
#: imports back through ``pptx_to_slides`` at that exact position, with no rounding drift to account for.
_UNIT_EMU = 7620


def build_heading_styles() -> bytes:
    document = docx.Document()
    document.add_paragraph("Claudia Field Notes", style="Title")
    document.add_paragraph("Introduction", style="Heading 1")
    document.add_paragraph("This is the introduction.")
    document.add_paragraph("Background", style="Heading 2")
    document.add_paragraph("More background text.")
    return _bytes(document)


def build_tracked_change_suggestion() -> bytes:
    document = docx.Document()
    document.add_paragraph("The committee rejected the proposal.")
    return _bytes(document)


def build_beyond_claudia_table() -> bytes:
    document = docx.Document()
    document.add_paragraph("Status report.")
    table = document.add_table(rows=2, cols=2)
    table.rows[0].cells[0].text = "Region"
    table.rows[0].cells[1].text = "Amount"
    table.rows[1].cells[0].text = "North"
    table.rows[1].cells[1].text = "120"
    document.add_paragraph("End of report.")
    return _bytes(document)


def build_beyond_claudia_image() -> bytes:
    document = docx.Document()
    document.add_paragraph("Photo attached.")
    document.add_picture(_red_square_png(), width=Inches(1))
    document.add_paragraph("See above.")
    return _bytes(document)


def _red_square_png() -> BytesIO:
    image = Image.new("RGB", (16, 16), color=(214, 71, 122))
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    buffer.seek(0)
    return buffer


def _bytes(document: docx.Document) -> bytes:
    out = BytesIO()
    document.save(out)
    return out.getvalue()


def _box(x: int, y: int, w: int, h: int) -> tuple[Emu, Emu, Emu, Emu]:
    """A claudia-unit box as the EMU box python-pptx wants, at this file's fixed 16:9 scale."""
    return Emu(x * _UNIT_EMU), Emu(y * _UNIT_EMU), Emu(w * _UNIT_EMU), Emu(h * _UNIT_EMU)


def _new_presentation() -> pptx.Presentation:
    """A blank 16:9 deck, same size ``claudia_creates_io.pptx.slides_to_pptx`` itself produces."""
    prs = pptx.Presentation()
    prs.slide_width, prs.slide_height = Emu(1600 * _UNIT_EMU), Emu(900 * _UNIT_EMU)
    return prs


def build_shapes_and_text() -> bytes:
    prs = _new_presentation()
    layout = prs.slide_layouts[6]  # blank
    slide1 = prs.slides.add_slide(layout)
    slide1.shapes.add_textbox(*_box(100, 80, 500, 120)).text_frame.text = "Welcome to Claudia"
    circle = slide1.shapes.add_shape(MSO_SHAPE.OVAL, *_box(700, 80, 200, 200))
    circle.text_frame.text = "Idea"
    slide2 = prs.slides.add_slide(layout)
    rectangle = slide2.shapes.add_shape(MSO_SHAPE.RECTANGLE, *_box(100, 500, 400, 200))
    rectangle.text_frame.text = "Box"
    return _pptx_bytes(prs)


def build_pptx_beyond_claudia_table() -> bytes:
    prs = _new_presentation()
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    slide.shapes.add_textbox(*_box(100, 80, 600, 120)).text_frame.text = "Status report."
    table_shape = slide.shapes.add_table(2, 2, *_box(100, 300, 600, 300))
    table_shape.table.cell(0, 0).text = "Region"
    table_shape.table.cell(0, 1).text = "Amount"
    table_shape.table.cell(1, 0).text = "North"
    table_shape.table.cell(1, 1).text = "120"
    return _pptx_bytes(prs)


def build_pptx_beyond_claudia_image() -> bytes:
    prs = _new_presentation()
    layout = prs.slide_layouts[6]
    slide1 = prs.slides.add_slide(layout)
    slide1.shapes.add_textbox(*_box(100, 80, 600, 120)).text_frame.text = "Photo attached."
    slide2 = prs.slides.add_slide(layout)
    slide2.shapes.add_picture(_red_square_png(), *_box(100, 100, 300, 300))
    return _pptx_bytes(prs)


def _pptx_bytes(prs: pptx.Presentation) -> bytes:
    out = BytesIO()
    prs.save(out)
    return out.getvalue()


def build_cells_and_formulas() -> bytes:
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Data"
    ws.append(["Region", "Product", "Amount"])
    for region, product, amount in (
        ("North", "Widget", 100),
        ("North", "Gadget", 150),
        ("South", "Widget", 200),
        ("South", "Gadget", 120),
        ("East", "Widget", 130),
        ("West", "Gadget", 140),
    ):
        ws.append([region, product, amount])
    ws.append(["Total", None, "=SUM(C2:C7)"])
    notes = wb.create_sheet("Notes")
    notes["A1"] = "Six regions, two products."
    return _xlsx_bytes(wb)


def build_xlsx_beyond_claudia_chart() -> bytes:
    wb = openpyxl.Workbook()
    data = wb.active
    data.title = "Data"
    data.append(["Region", "Amount"])
    for region, amount in (("North", 100), ("South", 200), ("East", 130)):
        data.append([region, amount])
    chart_sheet = wb.create_sheet("Chart")
    chart = BarChart()
    chart.add_data(Reference(data, min_col=2, min_row=1, max_row=4), titles_from_data=True)
    chart.set_categories(Reference(data, min_col=1, min_row=2, max_row=4))
    chart_sheet.add_chart(chart, "A1")
    return _xlsx_bytes(wb)


def build_xlsx_beyond_claudia_image() -> bytes:
    wb = openpyxl.Workbook()
    data = wb.active
    data.title = "Data"
    data["A1"] = "North"
    pics = wb.create_sheet("Pics")
    pics.add_image(XLImage(_red_square_png()), "A1")
    return _xlsx_bytes(wb)


def _xlsx_bytes(wb: openpyxl.Workbook) -> bytes:
    out = BytesIO()
    wb.save(out)
    return out.getvalue()


FIXTURES = {
    "docx/heading-styles/source.docx": build_heading_styles,
    "docx/tracked-change-suggestion/source.docx": build_tracked_change_suggestion,
    "docx/beyond-claudia/table/source.docx": build_beyond_claudia_table,
    "docx/beyond-claudia/image/source.docx": build_beyond_claudia_image,
    "pptx/shapes-and-text/source.pptx": build_shapes_and_text,
    "pptx/beyond-claudia/table/source.pptx": build_pptx_beyond_claudia_table,
    "pptx/beyond-claudia/image/source.pptx": build_pptx_beyond_claudia_image,
    "xlsx/cells-and-formulas/source.xlsx": build_cells_and_formulas,
    "xlsx/beyond-claudia/chart/source.xlsx": build_xlsx_beyond_claudia_chart,
    "xlsx/beyond-claudia/image/source.xlsx": build_xlsx_beyond_claudia_image,
}


def main() -> None:
    for relative_path, build in FIXTURES.items():
        path = ROOT / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(build())
        print(f"wrote {relative_path}")


if __name__ == "__main__":
    main()
