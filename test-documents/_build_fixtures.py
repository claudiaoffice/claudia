"""Regenerates every checked-in ``source.docx`` in this library, deterministically (D178).

A test document is checked in as a real, openable binary -- not just a Python function that builds one on the
fly, the way every other format test in this repo does -- because the whole point of a *library* is files a
person (or LibreOffice, or real Word) can open directly, not just assertions about one. This script is how they
were made, and how to remake or extend them: nobody hand-edits a ``source.docx``.

``uv run python test-documents/_build_fixtures.py``
"""

from __future__ import annotations

from io import BytesIO
from pathlib import Path

import docx
from docx.shared import Inches
from PIL import Image

ROOT = Path(__file__).resolve().parent


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


FIXTURES = {
    "docx/heading-styles/source.docx": build_heading_styles,
    "docx/tracked-change-suggestion/source.docx": build_tracked_change_suggestion,
    "docx/beyond-claudia/table/source.docx": build_beyond_claudia_table,
    "docx/beyond-claudia/image/source.docx": build_beyond_claudia_image,
}


def main() -> None:
    for relative_path, build in FIXTURES.items():
        path = ROOT / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(build())
        print(f"wrote {relative_path}")


if __name__ == "__main__":
    main()
