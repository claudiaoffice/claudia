"""Open OpenDocument output in LibreOffice, the reference implementation, and check what it reads (D409).

``uv run python scripts/odf_libreoffice_check.py``

What the unit tests prove is that the files follow the rules this code knows. This asks a program that is not this
code. For every enabled odt, odp and ods entry of the test-document library it makes the edit the entry's
``spec.py`` makes, and for a model with every style and a suggestion, a deck with a text box and the three shapes and
a workbook with formulas it makes a new file; then it has ``soffice --headless`` convert the source, the edited file
and the new file -- an odt to plain text, an odp to a PowerPoint file, whose shapes and words are then listed, an ods
to an Excel file whose cells are then read -- and checks that

* ``soffice`` accepts the file (exit code 0, a file comes out),
* every word of every block (every object) of the edited model is in what LibreOffice read, in order. (Words, not
  the exact text: LibreOffice prints a footnote's number inside the sentence and a tracked deletion and its insertion
  run together, and writes a tab or a break as it likes.), and
* every cell of an edited or new workbook has in LibreOffice the value the model computes for it -- also where the
  value is a formula's, so a formula LibreOffice reads differently from what was meant shows (D413).

It exits 0 where there is no ``soffice`` (saying so: a skip is never reported as a pass) and 1 if any check failed. The
CI job that runs it is allowed to fail at first (D409); a run on a laptop with LibreOffice installed is the check.
"""

from __future__ import annotations

import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LIBRARY = ROOT / "test-documents"
TIMEOUT = 180


def soffice() -> str | None:
    return shutil.which("soffice") or shutil.which("libreoffice")


def convert(program: str, data: bytes, work: Path, fmt: str) -> Path:
    """What ``soffice`` makes of the ``fmt`` file ``data``: text for an odt, a pptx for an odp, an xlsx for an ods."""
    source = work / f"in.{fmt}"
    source.write_bytes(data)
    out = work / "out"
    out.mkdir(exist_ok=True)
    profile = work / "profile"  # a profile of its own, so no run waits for another's lock
    target, extension = {"odt": ("txt:Text", "txt"), "odp": ("pptx", "pptx"), "ods": ("xlsx", "xlsx")}[fmt]
    command = [
        program,
        f"-env:UserInstallation=file://{profile}",
        "--headless",
        "--convert-to",
        target,
        "--outdir",
        str(out),
        str(source),
    ]
    done = subprocess.run(command, capture_output=True, text=True, timeout=TIMEOUT, check=False)
    produced = out / f"in.{extension}"
    if done.returncode != 0 or not produced.exists():
        raise RuntimeError(f"soffice could not read the file (exit {done.returncode}): {done.stderr.strip()[:300]}")
    return produced


def words_of_slides(path: Path) -> str:
    """Every word on every slide of a pptx, in the order of the shapes (groups included)."""
    from pptx import Presentation

    def walk(shapes):
        for shape in shapes:
            if shape.shape_type == 6:  # a group
                yield from walk(shape.shapes)
            elif shape.has_text_frame:
                yield shape.text_frame.text

    return "\n".join(text for slide in Presentation(str(path)).slides for text in walk(slide.shapes))


def as_text(program: str, data: bytes, work: Path, fmt: str = "odt") -> str:
    """What LibreOffice reads of the ``fmt`` file ``data``, as plain text."""
    produced = convert(program, data, work, fmt)
    if fmt == "odt":
        return produced.read_text(encoding="utf-8-sig")
    if fmt == "ods":
        return ""  # a workbook is compared cell by cell, see ``wrong_cells``
    return words_of_slides(produced)


def wrong_cells(program: str, data: bytes, work: Path, model) -> list[str]:
    """The cells of ``model`` whose value LibreOffice reads differently from the model's own (empty if it agrees)."""
    from datetime import datetime

    from openpyxl import load_workbook
    from openpyxl.utils.datetime import to_excel

    from claudia_computes.values import ErrorValue

    book = load_workbook(convert(program, data, work, "ods"), data_only=True)
    wrong = []
    for sheet_id, sheet in model.sheets.items():
        if sheet.name not in book.sheetnames:
            wrong.append(f"sheet {sheet.name!r} is missing")
            continue
        worksheet = book[sheet.name]
        for row, column in sheet.cells:
            expected = model.value(sheet_id, row, column)
            read = worksheet.cell(row=row + 1, column=column + 1).value
            if isinstance(read, datetime):
                read = to_excel(read)
            if isinstance(expected, ErrorValue):
                good = read == expected.code
            elif isinstance(expected, bool) or not isinstance(expected, int | float):
                good = read == expected or (expected in ("", None) and read in ("", None))
            else:
                good = isinstance(read, int | float) and abs(read - expected) <= 1e-9 * max(1.0, abs(expected))
            if not good:
                wrong.append(f"{sheet.name}!R{row + 1}C{column + 1}: model {expected!r}, LibreOffice {read!r}")
    return wrong


def shows(read: str, expected: str) -> bool:
    """Whether every word of ``expected`` is in ``read``, in order (see the module description)."""
    position = 0
    for word in re.findall(r"\w+", expected):
        found = read.find(word, position)
        if found < 0:
            return False
        position = found + len(word)
    return True


def texts_of(fmt: str, model) -> list[str]:
    """The words of ``model`` the file must show, one entry per block or object."""
    if fmt == "odt":
        return [block.text for block in model.blocks if block.text.strip()]
    return [
        o.body.paragraph.text
        for slide in model.slides
        for o in model.objects_on(slide)
        if o.body.paragraph is not None and o.body.paragraph.text.strip()
    ]


def library_cases() -> list[tuple[str, str, bytes, bytes, object]]:
    """``(name, format, source, edited, what the edited file must show)`` for each enabled odt, odp and ods entry: the
    words (a list) of an odt or odp, the workbook of an ods."""
    from claudia_test_documents import load_catalogue
    from claudia_test_documents.adapters import ADAPTERS
    from claudia_test_documents.loader import load_case

    found = []
    for entry in load_catalogue(LIBRARY / "catalogue.json"):
        fmt = entry["format"]
        if fmt not in ("odt", "odp", "ods") or not entry.get("enabled", True):
            continue
        adapter = ADAPTERS[fmt]
        assert adapter.apply_edits_fn is not None
        source = (LIBRARY / entry["source"]).read_bytes()
        case = load_case(LIBRARY / entry["spec"], entry["id"])
        baseline, working = adapter.import_fn(source), adapter.import_fn(source)
        current = case.modify(working) if case.modify is not None else working
        edited = adapter.apply_edits_fn(source, baseline, current)
        reread = adapter.import_fn(edited)
        found.append((entry["id"], fmt, source, edited, reread if fmt == "ods" else texts_of(fmt, reread)))
    return found


def new_file() -> tuple[bytes, list[str]]:
    """A file made from a model: every style, white space, a suggestion."""
    from claudia_composes_io import odt_to_text, text_to_odt

    from claudia_composes import Block, Suggestion, TextModel, TextRange

    model = TextModel(
        [
            Block("b1", "title", "Annual report"),
            Block("b2", "heading-1", "Summary"),
            Block("b3", "heading-2", "Details"),
            Block("b4", "body", "The committee rejected the proposal.  Two  spaces\tand a tab\nand a break."),
            Block("b5", "quote", "Words of someone else"),
        ]
    )
    model.suggestions["s1"] = Suggestion("s1", "Claudia AI", TextRange("b4", 14, 22), "rejected", "approved", "tone")
    data = text_to_odt(model)
    return data, [block.text for block in odt_to_text(data).blocks]


def new_deck() -> tuple[bytes, list[str]]:
    """A file made from a deck: a text box with two lines and the three shapes, one with words."""
    from claudia_creates_io import odp_to_slides, slides_to_odp

    from claudia_core import ObjectBody, VisualObject, paragraph_for
    from claudia_creates import ShapeLibrary, SlideAnchor, SlideModel
    from claudia_server.creates import PARAGRAPH_STYLE_OF_KIND, STYLE_OF_KIND

    def put(model, object_id, slide, kind, x, y, w, h, text="", shape=None):
        # The styles the server gives a new object (D304, D310): its container's and its words' are two slots, so a
        # shape is "plain-shape" (an outline) with "shape-label" words, a text box "plain-box" with "body-text".
        style, words = STYLE_OF_KIND[kind], PARAGRAPH_STYLE_OF_KIND[kind]
        body = ObjectBody(object_id, kind, w, h, style, paragraph_for(object_id, words, text, "ana"), shape=shape)
        model.insert_object(VisualObject(body, SlideAnchor(slide, x, y)))

    model, library = SlideModel(), ShapeLibrary.load()
    for shape_id in ("circle", "rectangle", "triangle"):
        model.define_shape(library.get(shape_id))
    model.insert_slide("s1")
    model.insert_slide("s2")
    put(model, "o1", "s1", "text", 160, 90, 800, 120, "Annual report\nSecond line & <more>")
    put(model, "o2", "s1", "shape", 1000, 200, 300, 300, "", "circle")
    put(model, "o3", "s2", "shape", 100, 100, 400, 200, "boxed", "rectangle")
    put(model, "o4", "s2", "shape", 700, 100, 200, 200, "tri", "triangle")
    data = slides_to_odp(model)
    return data, texts_of("odp", odp_to_slides(data))


def new_workbook() -> tuple[bytes, object]:
    """A file made from a workbook: numbers, text, a date, formulas (one with an error) and a second sheet."""
    from claudia_computes_io import ods_to_workbook, workbook_to_ods

    from claudia_computes import Sheet, SheetId, WorkbookModel

    model = WorkbookModel()
    first, second = Sheet(SheetId("s1"), "Data"), Sheet(SheetId("s2"), "Notes")
    for sheet in (first, second):
        model.add_sheet(sheet, None)
    put = model.store
    for row, (label, amount) in enumerate([("North", 100), ("South", 150.5), ("East", 200)], start=1):
        put(first, row, 0, {"t": "text", "v": label})
        put(first, row, 1, {"t": "int" if isinstance(amount, int) else "float", "v": amount})
    put(first, 0, 0, {"t": "text", "v": "Region"})
    put(first, 0, 1, {"t": "text", "v": "Amount"})
    put(first, 4, 1, {"t": "formula", "v": "=SUM(B2:B4)"})
    put(first, 5, 1, {"t": "formula", "v": '=IF(B5>400,ROUND(B5/3,2),"small")'})
    put(first, 6, 1, {"t": "formula", "v": "=1/0"})
    put(first, 7, 1, {"t": "formula", "v": "=Notes!A1*2"})
    put(second, 0, 0, {"t": "int", "v": 21})
    put(second, 1, 0, {"t": "bool", "v": True})
    model.calc.recalculate_all()
    data = workbook_to_ods(model)
    return data, ods_to_workbook(data)


def main() -> int:
    program = soffice()
    if program is None:
        print("skipped: soffice (LibreOffice) is not installed; nothing was checked")
        return 0
    library = library_cases()
    cases = [(name, fmt, edited, shown) for name, fmt, _, edited, shown in library]
    cases += [(f"{name} (source)", fmt, source, [] if fmt != "ods" else None) for name, fmt, source, _, _ in library]
    data, shown = new_file()
    cases.append(("new odt from a model", "odt", data, shown))
    data, shown = new_deck()
    cases.append(("new odp from a deck", "odp", data, shown))
    data, workbook = new_workbook()
    cases.append(("new ods from a workbook", "ods", data, workbook))
    failed = 0
    with tempfile.TemporaryDirectory() as directory:
        for name, fmt, data, texts in cases:
            work = Path(directory) / re.sub(r"\W+", "-", name)
            work.mkdir()
            try:
                if fmt == "ods":
                    wrong = wrong_cells(program, data, work, texts) if texts is not None else []
                    if texts is None:
                        convert(program, data, work, fmt)
                    if wrong:
                        raise RuntimeError("LibreOffice reads other values: " + "; ".join(wrong[:8]))
                else:
                    text = as_text(program, data, work, fmt)
                    missing = [t for t in texts if not shows(text, t)]
                    if missing:
                        raise RuntimeError(f"LibreOffice does not show: {missing}")
            except (RuntimeError, subprocess.TimeoutExpired) as problem:
                failed += 1
                print(f"FAIL  {name}: {problem}")
            else:
                print(f"ok    {name}")
    print(f"{len(cases) - failed} of {len(cases)} read by LibreOffice" + ("" if not failed else f", {failed} did not"))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
