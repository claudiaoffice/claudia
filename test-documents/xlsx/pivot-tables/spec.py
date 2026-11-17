"""A pivot table LibreOffice saved into an xlsx: a cache over a range of the data sheet, a pivot table of regions
down the side and quarters across with a sum of the amount, and its numbers in the cells. It comes in as a live pivot
of the model, because the engine makes the very cells the file shows. A number of the source edited gives the new
numbers in the cells; the pivot table definition stays as it is and the cache is asked to be read again when the file
is opened (D625, D628)."""

from __future__ import annotations

from claudia_computes import Aggregation, ValueField, WorkbookModel
from claudia_opc_io import read_parts
from claudia_test_documents.case import Case

PIVOT = "PivotSales"


def import_checks(model: WorkbookModel) -> None:
    entry = model.pivots.get(PIVOT)
    assert entry is not None, "the pivot table is read as a live one"
    assert (entry.definition.rows, entry.definition.columns) == (("Region",), ("Quarter",))
    assert entry.definition.values == (ValueField("Amount", Aggregation.SUM, "Sum - Amount"),)
    assert entry.labels.total == "Total Result"  # (the words are read off the file's own cells)
    assert model.value("s2", 7, 3) == 600


def modify(model: WorkbookModel) -> WorkbookModel:
    model.store(model.sheet("s1"), 1, 2, {"t": "int", "v": 1000})  # North, Q1: 100 -> 1000
    return model


def after_checks(model: WorkbookModel) -> None:
    assert model.pivots.get(PIVOT) is not None
    assert model.value("s2", 5, 1) == 1000
    assert model.value("s2", 7, 1) == 1140  # the total of Q1
    assert model.value("s2", 7, 3) == 1500


def cache_is_read_again(original: bytes, edited: bytes) -> None:
    assert b'refreshOnLoad="1"' in read_parts(edited)["xl/pivotCache/pivotCacheDefinition1.xml"]


CASE = Case(
    import_checks=import_checks,
    modify=modify,
    after_checks=after_checks,
    export_checks=lambda edited: cache_is_read_again(b"", edited),
    preserve_parts=["xl/pivotTables/pivotTable1.xml"],
)
