"""A pivot table LibreOffice made over a table of sales (regions down the side, quarters across, a sum of the amount,
a total row and column in LibreOffice's words). It comes in as a live pivot of the model, because the engine makes the
very cells the file shows; a number of the source edited gives the new numbers in the cells, and the pivot table of
the file stays as it is (D625, D628)."""

from __future__ import annotations

import re

from claudia_computes import Aggregation, ValueField, WorkbookModel
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


def pivot_stays(original: bytes, edited: bytes) -> None:
    from claudia_opc_io import read_parts

    def pilots(data: bytes) -> list[str]:
        text = read_parts(data)["content.xml"].decode()
        return re.findall(r"<table:data-pilot-table .*?</table:data-pilot-table>", text, re.DOTALL)

    assert pilots(original) and pilots(edited) == pilots(original), "the pivot table of the file is not rewritten"


CASE = Case(
    import_checks=import_checks,
    modify=modify,
    after_checks=after_checks,
    preserve_parts=["styles.xml", "META-INF/manifest.xml"],
    preserve_elements=pivot_stays,
)
