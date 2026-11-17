"""Workbooks with pivot tables for the file tests (D625, D628): the engine makes them, the way a person does."""

from __future__ import annotations

from dataclasses import replace

from claudia_computes import (
    AddSheet,
    CellRef,
    DefineName,
    NamedRange,
    PivotDefinition,
    PivotLabels,
    RangeRef,
    SetCells,
    ValueField,
    WorkbookModel,
    create_pivot,
    parse_input,
)
from claudia_core import Document, MemoryStore

SALES = (
    ("Region", "Quarter", "Amount", "Units"),
    ("North", "Q1", 100, 1),
    ("North", "Q2", 150, 2),
    ("South", "Q1", 80, 3),
    ("South", "Q2", 120, 4),
    ("East", "Q1", 60, 5),
)


def by_region_and_quarter(**changes) -> PivotDefinition:
    fields = {"source": "Sales", "rows": ("Region",), "columns": ("Quarter",), "values": (ValueField("Amount"),)}
    return PivotDefinition(**{**fields, **changes})


def a_document(
    rows=SALES, *, name: str | None = "Sales", pivot: PivotDefinition | None = None, labels=None
) -> Document:
    """A document with a sheet ``Data`` holding ``rows`` (and, unless ``name`` is ``None``, a table of them called
    ``name``), and a pivot called ``P`` on the sheet ``Pivot`` when ``pivot`` is given."""
    doc = Document(WorkbookModel(), store=MemoryStore())
    doc.execute(AddSheet("s1", "Data"), author="ana")
    cells = tuple(
        (r, c, parse_input(str(v)) if not isinstance(v, str) else parse_input(v))
        for r, row in enumerate(rows)
        for c, v in enumerate(row)
    )
    doc.execute(SetCells("s1", cells), author="ana")
    if name is not None:
        box = RangeRef.between(CellRef(0, 0, "s1"), CellRef(len(rows) - 1, len(rows[0]) - 1, "s1"))
        doc.execute(DefineName(NamedRange(name, None, box, True)), author="ana")
    if pivot is not None:
        doc.execute(create_pivot(doc.model, "P", ("s2", 0, 0), pivot, labels, new_sheet="Pivot"), author="ana")
    return doc


def a_pivot_model(definition: PivotDefinition | None = None, labels: PivotLabels | None = None) -> WorkbookModel:
    """The workbook of :func:`a_document` with the pivot ``P`` on the sheet ``Pivot``, calculated."""
    return a_document(pivot=definition or by_region_and_quarter(), labels=labels).model


def grid_of(model: WorkbookModel, sheet: str, height: int, width: int, *, row: int = 0, col: int = 0) -> list[list]:
    """The values of a rectangle of a sheet, as the model shows them."""
    return [[model.value(sheet, row + r, col + c) for c in range(width)] for r in range(height)]


def a_headerless_pivot_model() -> WorkbookModel:
    """A pivot over a range with no header row (its columns are A, B, C...): a file cannot hold it as a pivot."""
    doc = a_document(name="Raw")
    raw = doc.model.names.get((None, "raw"))
    assert raw is not None
    doc.model.names.put(replace(raw, header=False))
    definition = by_region_and_quarter(source="Raw", rows=("A",), columns=("B",), values=(ValueField("C"),))
    doc.execute(create_pivot(doc.model, "P", ("s2", 0, 0), definition, None, new_sheet="Pivot"), author="ana")
    return doc.model
