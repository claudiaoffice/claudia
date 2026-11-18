"""Redacting an imported workbook (D723): cells, chart titles and objects go; sheets, names and places stay."""

import json

import pytest

from claudia_computes import AddSheet, SetCells, WorkbookModel
from claudia_core import Document, Import, MemoryStore, RedactionError, Revision

SECRET = "IBAN DE89 3704 0044 0532 0130 00"


def text(words: str) -> dict:
    return {"t": "text", "v": words}


def workbook() -> WorkbookModel:
    doc = Document(WorkbookModel(), store=MemoryStore())
    doc.execute(AddSheet("s1", "Pay"), author="ana")
    doc.execute(
        SetCells("s1", ((0, 0, text("Name")), (1, 0, text(SECRET)), (1, 1, {"t": "int", "v": 4200}))), author="ana"
    )
    return doc.model


def imported() -> Document:
    doc = Document(WorkbookModel(), store=MemoryStore())
    doc.execute(Import("pay.xlsx", "xlsx", workbook().serialize(), "ab" * 32, True), author="ana")
    doc.execute(SetCells("s1", ((2, 0, text("Total")), (2, 1, {"t": "formula", "v": "SUM(B1:B2)"}))), author="ben")
    return doc


def cells(doc: Document) -> dict:
    return dict(doc.model.sheets["s1"].cells)


def test_an_imported_workbook_is_blanked_in_full():
    doc = imported()
    doc.redact(doc.plan_redaction([Revision("main", 1)]), author="ana")
    assert set(cells(doc)) == {(2, 0), (2, 1)} and cells(doc)[(2, 0)] == text("Total")
    assert doc.model.sheets["s1"].name == "Pay"
    assert SECRET not in json.dumps(doc.log.to_data())


def test_an_imported_workbook_is_blanked_in_parts():
    doc = imported()
    doc.redact(doc.plan_redaction([Revision("main", 1)], parts={Revision("main", 1): ["s1!A2"]}), author="ana")
    assert (1, 0) not in cells(doc) and cells(doc)[(1, 1)]["v"] == 4200 and cells(doc)[(0, 0)] == text("Name")


def test_a_part_the_workbook_does_not_have_is_named():
    doc = imported()
    for part in ("s9", "s9!A1", "nothing"):
        with pytest.raises(RedactionError) as caught:
            doc.plan_redaction([Revision("main", 1)], parts={Revision("main", 1): [part]})
        assert "s9" in str(caught.value) or "nothing" in str(caught.value)


def corner(row: int, col: int) -> dict:
    return {"row": row, "col": col, "sheet": "s1", "row_abs": False, "col_abs": False}


def test_a_chart_keeps_what_it_reads_but_not_its_titles():
    blank = WorkbookModel.blank_diagram(
        {
            "format": 1,
            "id": "c1",
            "kind": "bar",
            "range": {"first": corner(0, 0), "last": corner(2, 1)},
            "series_in": "columns",
            "header_row": True,
            "title": "Salaries 2026",
            "x_title": "who",
            "y_title": "how much",
            "legend": True,
            "gridlines": True,
        }
    )
    assert (blank["title"], blank["x_title"], blank["y_title"]) == ("", "", "")
    assert blank["range"]["last"]["row"] == 2


def test_a_plan_names_the_places_that_change_now():
    """What a preview marks (D721): the cells the blanked step touched, on the line people see."""
    doc = Document(WorkbookModel(), store=MemoryStore())
    doc.execute(AddSheet("s1", "Pay"), author="ana")
    doc.execute(SetCells("s1", ((1, 0, text(SECRET)),)), author="ben")
    plan = doc.plan_redaction([Revision("main", 2)])
    cells = [r.to_data() for r in plan.regions if r.to_data()["kind"] == "cells"]
    assert cells and cells[0]["range"]["first"]["row"] == 1
    gone = Document(WorkbookModel(), store=MemoryStore())
    gone.execute(AddSheet("s1", "Pay"), author="ana")
    gone.execute(SetCells("s1", ((1, 0, text(SECRET)),)), author="ben")
    gone.execute(SetCells("s1", ((1, 0, None),)), author="ben")
    assert gone.plan_redaction([Revision("main", 2)]).regions == ()  # nothing people see changes
