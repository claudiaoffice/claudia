"""RANDOM distributions and alternatives in ods files: what OpenDocument gets, what comes back, what is counted."""

from __future__ import annotations

import csv
import shutil
import subprocess

import pytest
from claudia_computes_io import (
    apply_edits_to_ods,
    ods_export_losses,
    ods_import_losses,
    ods_to_workbook,
    workbook_to_ods,
)
from test_ods import an_ods, row, table
from test_ods import formula as ods_formula

from claudia_computes import Sheet, SheetId, WorkbookModel
from claudia_opc_io import read_parts, write_parts


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


def kinds(losses) -> dict[str, int]:
    return {(f"{loss.kind}:{loss.detail}" if loss.detail else loss.kind): loss.count for loss in losses}


def content_xml(data: bytes) -> str:
    return read_parts(data)["content.xml"].decode()


MODEL = {
    (0, 0): formula("=ALTERNATIVES(800,1000,1300)"),
    (1, 0): formula('=RANDOM("normal",1000,150)'),
    (2, 0): formula("=A1*2+RAND()"),
    (3, 0): formula('=RANDOM("lognormal",0,0.5)+A1'),
}


def test_a_distribution_is_written_as_an_openformula_that_draws_it():
    xml = content_xml(workbook_to_ods(model_of(MODEL)))
    assert 'table:formula="of:=NORMINV(RAND();1000;150)"' in xml
    assert 'table:formula="of:=LOGINV(RAND();0;0.5)+[.A1]"' in xml


def test_alternatives_are_their_first_value_and_a_comment_in_the_file():
    xml = content_xml(workbook_to_ods(model_of(MODEL)))
    assert "claudia alternatives: {800, 1000, 1300}" in xml
    assert "<office:annotation" in xml


def test_a_draw_written_as_plain_arithmetic_comes_back_as_that_arithmetic():
    """Excel has no inverse function for these: the model reads what it was given, which draws the same numbers."""
    again = ods_to_workbook(workbook_to_ods(model_of({(0, 0): formula('=RANDOM("weibull",1.5,10)')})))
    assert cells(again)[(0, 0)] == formula("=10*(-LN(1-RAND()))^(1/1.5)")


def test_a_round_trip_gives_everything_back():
    again = ods_to_workbook(workbook_to_ods(model_of(MODEL)))
    assert cells(again) == {
        (0, 0): formula("=ALTERNATIVES(800,1000,1300)"),
        (1, 0): formula('=RANDOM("normal",1000,150)'),
        (2, 0): formula("=A1*2+RAND()"),
        (3, 0): formula('=RANDOM("lognormal",0,0.5)+A1'),
    }


def test_the_note_is_not_reported_as_a_comment_that_was_lost():
    data = workbook_to_ods(model_of(MODEL))
    assert "comment" not in kinds(ods_import_losses(data))


def test_what_is_written_that_only_claudia_reads_is_reported():
    model = model_of({**MODEL, (4, 0): formula('=RANDOM("triangular",1,2,3)'), (5, 0): formula('=RANDOM("poisson",3)')})
    assert kinds(ods_export_losses(model)) == {"formula:random": 2, "alternatives": 1}


def test_a_draw_openformula_has_no_formula_for_is_written_as_its_value():
    model = model_of({(0, 0): formula('=RANDOM("triangular",1,2,3)')})
    xml = content_xml(workbook_to_ods(model))
    assert "table:formula" not in xml and 'office:value-type="float"' in xml


def test_a_comment_of_somebody_else_is_still_a_lost_comment():
    data = workbook_to_ods(model_of({(0, 0): {"t": "int", "v": 5}}))
    xml = content_xml(data).replace(
        '<table:table-cell office:value-type="float" office:value="5">',
        '<table:table-cell office:value-type="float" office:value="5"><office:annotation>'
        "<text:p>check this</text:p></office:annotation>",
    )
    parts = read_parts(data)
    parts["content.xml"] = xml.encode()
    edited = write_parts(parts)
    assert kinds(ods_import_losses(edited)) == {"comment": 1}
    assert cells(ods_to_workbook(edited))[(0, 0)] == {"t": "int", "v": 5}


def test_a_file_from_another_program_with_inverse_functions_reads_as_random():
    data = an_ods(
        table(
            "Pricing",
            row(
                ods_formula("of:=NORMINV(RAND();[.B1];[.B2])", "3"),
                ods_formula("of:=COM.MICROSOFT.BINOM.INV(10;0.5;RAND())", "4"),
                ods_formula("of:=NORMINV(0.5;1;2)", "1"),  # (an inverse that is not of a draw: the model lacks it)
            ),
        )
    )
    read = ods_to_workbook(data)
    assert cells(read)[(0, 0)] == formula('=RANDOM("normal",B1,B2)')
    assert cells(read)[(0, 1)] == formula('=RANDOM("binomial",10,0.5)')
    assert cells(read)[(0, 2)] == {"t": "int", "v": 1}
    assert kinds(ods_import_losses(data)) == {"formula:function": 1}


def test_an_edited_import_writes_alternatives_and_draws_the_same_way():
    original = workbook_to_ods(model_of({(0, 0): {"t": "int", "v": 1}}))
    baseline, current = ods_to_workbook(original), ods_to_workbook(original)
    sheet = current.sheets[SheetId("s1")]
    sheet.cells[(0, 1)] = formula("=ALTERNATIVES(5,6,7)")
    sheet.cells[(0, 2)] = formula('=RANDOM("lognormal",0,0.5)')
    current._calculate_loaded()  # noqa: SLF001
    patched = apply_edits_to_ods(original, baseline, current)
    xml = content_xml(patched)
    assert "claudia alternatives: {5, 6, 7}" in xml and "LOGINV(RAND();0;0.5)" in xml
    again = cells(ods_to_workbook(patched))
    assert again[(0, 1)] == formula("=ALTERNATIVES(5,6,7)")
    assert again[(0, 2)] == formula('=RANDOM("lognormal",0,0.5)')


def test_changing_alternatives_back_to_a_number_takes_the_note_away():
    original = workbook_to_ods(model_of({(0, 0): formula("=ALTERNATIVES(5,6,7)")}))
    baseline, current = ods_to_workbook(original), ods_to_workbook(original)
    current.sheets[SheetId("s1")].cells[(0, 0)] = {"t": "int", "v": 9}
    current._calculate_loaded()  # noqa: SLF001
    patched = apply_edits_to_ods(original, baseline, current)
    assert "claudia alternatives" not in content_xml(patched)
    assert cells(ods_to_workbook(patched))[(0, 0)] == {"t": "int", "v": 9}


@pytest.mark.skipif(shutil.which("soffice") is None, reason="LibreOffice is not installed")
def test_libreoffice_calculates_what_we_write(tmp_path):
    lines = {
        "normal": ('=RANDOM("normal",1000,1)', 990, 1010),
        "beta": ('=RANDOM("beta",2,5)', 0, 1),
        "binomial": ('=RANDOM("binomial",20,0.3)', 0, 20),
        "discrete": ('=RANDOM("discrete",1,1,2,2,5,1)', 1, 5),
        "cut normal": ('=RANDOM("normal",1000,150,900,1100)', 900, 1100),
        "alternatives": ("=ALTERNATIVES(800,1000,1300)", 800, 800),
    }
    model = model_of({(i, 0): formula(text) for i, (text, _, _) in enumerate(lines.values())})
    path = tmp_path / "draws.ods"
    path.write_bytes(workbook_to_ods(model))
    subprocess.run(
        ["soffice", "--headless", "--convert-to", "csv", "--outdir", str(tmp_path), str(path)],
        check=True,
        capture_output=True,
        timeout=180,
    )
    shown = [row[0] for row in csv.reader((tmp_path / "draws.csv").open())]
    for (name, (_, low, high)), text in zip(lines.items(), shown, strict=True):
        assert low <= float(text) <= high, f"{name}: {text}"
