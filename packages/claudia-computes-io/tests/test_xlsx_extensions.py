"""RANDOM distributions and alternatives in xlsx files: what Excel gets, what comes back, what is counted as lost."""

from __future__ import annotations

import csv
import shutil
import subprocess
from io import BytesIO

import openpyxl
import pytest
from claudia_computes_io import apply_edits_to_xlsx, workbook_to_xlsx, xlsx_export_losses, xlsx_to_workbook
from openpyxl.comments import Comment

from claudia_computes import Sheet, SheetId, WorkbookModel


def model_of(cells: dict[tuple[int, int], dict]) -> WorkbookModel:
    model = WorkbookModel()
    sheet = Sheet(SheetId("s1"), "Pricing")
    sheet.cells.update(cells)
    model.sheets[sheet.id] = sheet
    model.open_container("s1")
    model._calculate_loaded()  # noqa: SLF001
    return model


def formula(text: str) -> dict:
    return {"t": "formula", "v": text}


def cells(model: WorkbookModel) -> dict:
    return dict(model.sheets[SheetId("s1")].cells)


def worksheet(data: bytes):
    return openpyxl.load_workbook(BytesIO(data))["Pricing"]


PRICING = {
    (0, 0): {"t": "text", "v": "Units"},
    (0, 1): formula("=ALTERNATIVES(800,1000,1300)"),
    (1, 1): {"t": "int", "v": 24},
    (2, 1): formula("=B1*B2"),
    (3, 1): formula('=RANDOM("normal",1000,150)'),
    (4, 1): formula('=RANDOM("pert",10,12,20)+B2'),
    (5, 1): formula("=RAND()+RANDBETWEEN(1,6)"),
}


def test_a_distribution_goes_to_excel_as_the_formula_that_draws_it():
    ws = worksheet(workbook_to_xlsx(model_of(PRICING)))
    assert ws["B4"].value == "=NORMINV(RAND(),1000,150)"
    assert ws["B5"].value == "=(10+(20-10)*BETAINV(RAND(),1+4*(12-10)/(20-10),1+4*(20-12)/(20-10)))+B2"
    assert ws["B6"].value == "=RAND()+RANDBETWEEN(1,6)"


def test_what_excel_has_for_the_draw_comes_back_as_random():
    again = xlsx_to_workbook(workbook_to_xlsx(model_of(PRICING)))
    assert cells(again)[(3, 1)] == formula('=RANDOM("normal",1000,150)')
    assert cells(again)[(5, 1)] == formula("=RAND()+RANDBETWEEN(1,6)")


def test_alternatives_are_the_first_value_and_a_note_in_the_file():
    ws = worksheet(workbook_to_xlsx(model_of(PRICING)))
    assert ws["B1"].value == 800
    assert ws["B1"].comment.text == "claudia alternatives: {800, 1000, 1300}"
    assert ws["B2"].comment is None


def test_alternatives_come_back_from_the_note():
    again = xlsx_to_workbook(workbook_to_xlsx(model_of(PRICING)))
    assert cells(again)[(0, 1)] == formula("=ALTERNATIVES(800,1000,1300)")


def test_a_number_changed_in_the_other_program_wins_over_the_note():
    data = workbook_to_xlsx(model_of(PRICING))
    wb = openpyxl.load_workbook(BytesIO(data))
    wb["Pricing"]["B1"].value = 950
    out = BytesIO()
    wb.save(out)
    assert cells(xlsx_to_workbook(out.getvalue()))[(0, 1)] == {"t": "int", "v": 950}


def test_a_comment_of_somebody_else_is_not_alternatives():
    data = workbook_to_xlsx(model_of({(0, 0): {"t": "int", "v": 5}}))
    wb = openpyxl.load_workbook(BytesIO(data))
    wb["Pricing"]["A1"].comment = Comment("check this", "ana")
    out = BytesIO()
    wb.save(out)
    assert cells(xlsx_to_workbook(out.getvalue()))[(0, 0)] == {"t": "int", "v": 5}


def test_named_alternatives_and_formulas_in_them_survive():
    model = model_of({(0, 0): {"t": "int", "v": 100}, (0, 1): formula('=SCENARIOS("low",A1*0.9,"base",A1)')})
    again = xlsx_to_workbook(workbook_to_xlsx(model))
    assert cells(again)[(0, 1)] == formula('=SCENARIOS("low",A1*0.9,"base",A1)')


def test_a_draw_excel_has_no_formula_for_is_written_as_its_value_and_counted():
    model = model_of({(0, 0): formula('=RANDOM("triangular",1,2,3)'), (1, 0): formula('=RANDOM("poisson",4)')})
    ws = worksheet(workbook_to_xlsx(model))
    assert isinstance(ws["A1"].value, float) and 1 <= ws["A1"].value <= 3
    assert isinstance(ws["A2"].value, int)
    losses = {(loss.kind, loss.detail): loss.count for loss in xlsx_export_losses(model)}
    assert losses == {("formula", "random"): 2}


def test_alternatives_are_counted_as_a_loss_because_only_claudia_reads_them():
    losses = {(loss.kind, loss.detail): loss.count for loss in xlsx_export_losses(model_of(PRICING))}
    assert losses == {("alternatives", ""): 1}


def test_a_file_from_excel_with_inverse_functions_reads_as_random():
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Pricing"
    ws["A1"] = "=_xlfn.NORM.INV(RAND(),B1,B2)"
    ws["A2"] = "=CRITBINOM(10,0.5,RAND())"
    out = BytesIO()
    wb.save(out)
    read = cells(xlsx_to_workbook(out.getvalue()))
    assert read[(0, 0)] == formula('=RANDOM("normal",B1,B2)')
    assert read[(1, 0)] == formula('=RANDOM("binomial",10,0.5)')


def test_editing_an_imported_file_writes_the_same_way():
    original = workbook_to_xlsx(model_of({(0, 0): {"t": "int", "v": 1}}))
    baseline = xlsx_to_workbook(original)
    current = xlsx_to_workbook(original)
    sheet = current.sheets[SheetId("s1")]
    sheet.cells[(0, 1)] = formula("=ALTERNATIVES(5,6,7)")
    sheet.cells[(0, 2)] = formula('=RANDOM("lognormal",0,0.5)')
    current._calculate_loaded()  # noqa: SLF001
    patched = apply_edits_to_xlsx(original, baseline, current)
    ws = worksheet(patched)
    assert ws["B1"].value == 5 and ws["B1"].comment.text == "claudia alternatives: {5, 6, 7}"
    assert ws["C1"].value == "=LOGINV(RAND(),0,0.5)"
    again = cells(xlsx_to_workbook(patched))
    assert again[(0, 1)] == formula("=ALTERNATIVES(5,6,7)")
    assert again[(0, 2)] == formula('=RANDOM("lognormal",0,0.5)')


@pytest.mark.skipif(shutil.which("soffice") is None, reason="LibreOffice is not installed")
def test_libreoffice_calculates_every_distribution_we_write(tmp_path):
    """A real spreadsheet program reads the formulas and draws plausible numbers from them."""
    lines = {
        "uniform": ('=RANDOM("uniform",10,20)', 10, 20),
        "normal": ('=RANDOM("normal",1000,1)', 990, 1010),
        "lognormal": ('=RANDOM("lognormal",0,0.1)', 0.5, 2),
        "exponential": ('=RANDOM("exponential",2)', 0, 100),
        "weibull": ('=RANDOM("weibull",1.5,10)', 0, 200),
        "beta": ('=RANDOM("beta",2,5)', 0, 1),
        "gamma": ('=RANDOM("gamma",3,2)', 0, 100),
        "pert": ('=RANDOM("pert",10,12,20)', 10, 20),
        "binomial": ('=RANDOM("binomial",20,0.3)', 0, 20),
        "discrete": ('=RANDOM("discrete",1,1,2,2,5,1)', 1, 5),
        "cut normal": ('=RANDOM("normal",1000,150,900,1100)', 900, 1100),
        "cut weibull": ('=RANDOM("weibull",1.5,10,2,5)', 2, 5),
        "cut pert": ('=RANDOM("pert",10,12,20,11,15)', 11, 15),
    }
    model = model_of({(i, 0): formula(text) for i, (text, _, _) in enumerate(lines.values())})
    path = tmp_path / "draws.xlsx"
    path.write_bytes(workbook_to_xlsx(model))
    subprocess.run(
        ["soffice", "--headless", "--convert-to", "csv", "--outdir", str(tmp_path), str(path)],
        check=True,
        capture_output=True,
        timeout=180,
    )
    shown = [row[0] for row in csv.reader((tmp_path / "draws.csv").open())]
    for (name, (_, low, high)), text in zip(lines.items(), shown, strict=True):
        value = float(text)
        assert low <= value <= high, f"{name}: {text}"
