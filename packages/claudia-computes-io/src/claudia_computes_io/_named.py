"""What a file can hold of the model's names, the same for every format (D457).

A name is a range of cells with a text, and perhaps a header row that makes it a *table*. Every file format holds the
range and the table; what it cannot hold of a name it is told so with a loss (code ``name``, detail below):

``result``
    A name a ``SQL()`` formula filled: the file has the formula (written as its value) and no rectangle to name.
``purpose``
    A table's colours by purpose and the row it grows by: only Claudia knows them.
``table-scope``
    A table of one sheet: files have tables of the workbook, so the range is written as a name of that sheet and
    loses its header row.
"""

from __future__ import annotations

from claudia_computes import NamedRange, WorkbookModel
from claudia_computes.names import DEFAULT_PURPOSE
from claudia_odf_io import LossLog

RESULT, PURPOSE, TABLE_SCOPE = "result", "purpose", "table-scope"


def is_table(named: NamedRange) -> bool:
    """Whether a file can hold ``named`` as a table: a range of the workbook with a header row."""
    return named.range is not None and named.header and named.scope is None


def writable(model: WorkbookModel) -> list[NamedRange]:
    """The names of ``model`` a file can hold, workbook-wide ones first: ranges that are on a sheet that exists."""
    return [
        named
        for named in model.names.sorted()
        if named.range is not None and named.range.sheet in model.sheets and named.scope in (None, *model.sheets)
    ]


def _colours(named: NamedRange) -> bool:
    return bool(named.grows or named.purpose != DEFAULT_PURPOSE or named.column_purposes)


def _is_news(named: NamedRange, before: WorkbookModel | None) -> bool:
    return before is None or before.names.get(named.key) != named


def unheld(model: WorkbookModel, baseline: WorkbookModel | None) -> LossLog:
    """What a file cannot hold of the names that are new or changed since ``baseline`` (``None``: the start of a fresh
    file), as losses of code ``name``."""
    losses = LossLog()
    for named in model.names:
        if not _is_news(named, baseline):
            continue
        if named.is_result:
            losses.add("name", RESULT)
            continue
        if named.header and named.scope is not None:
            losses.add("name", TABLE_SCOPE)
        if _colours(named):
            losses.add("name", PURPOSE)
    return losses
