"""A pivot table as the SQL query it is (E6.30, D621).

SQLite has no ``PIVOT``, and a query's columns are fixed when it is written, while a pivot's columns are the members
the column field has *now*. So a pivot is two queries: :func:`member_query` asks which members there are, and
:func:`pivot_query` is written with one ``CASE`` column for each of them. The text is plain SQL with its members
written out (never bound), so what a person is shown as "the pivot as SQL" is exactly what runs, and can be run by
itself: as a ``SQL()`` formula it gives the same cells as the pivot (D625).

SQLite has no ``ROLLUP`` either: the total row is a second ``SELECT`` over the same rows, joined with ``UNION ALL``.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass
from enum import Enum

from .pivot import PivotDefinition, PivotFilter, PivotLabels
from .sql import column_names, quoted
from .values import Value

_ONE_LINE = 72  # the longest the outer SELECT of a pivot with a total row may be on one line


class Span(Enum):
    """What a data column covers: one member of the column field, all of the rows, or the total of its members."""

    MEMBER = "member"
    ALL = "all"
    TOTAL = "total"


@dataclass(frozen=True, slots=True)
class DataColumn:
    """One column of numbers in a pivot: the ``value`` field (an index into the definition's) over a ``span``."""

    span: Span
    value: int
    member: Value = None


def literal(value: Value) -> str:
    """``value`` as an SQL literal. Members come from the source's own cells, so they are written out with their
    quotes doubled, and nothing a cell holds can be anything but text or a number in the query."""
    if value is None:
        return "NULL"
    if isinstance(value, bool):
        return "1" if value else "0"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        if math.isinf(value):
            return "9e999" if value > 0 else "-9e999"  # (what SQLite reads as infinity)
        return repr(value)
    if isinstance(value, str):
        return "'" + value.replace("'", "''") + "'"
    raise TypeError(f"no SQL literal for {value!r}")


def ordering(name: str) -> str:
    """Members in the order a pivot shows them: numbers, then text without regard to case, then the blank ones."""
    return f"{quoted(name)} IS NULL, {quoted(name)} COLLATE NOCASE, {quoted(name)}"


def where_lines(filters: Sequence[PivotFilter], indent: str = "") -> list[str]:
    """The ``WHERE`` that keeps what the filters keep: nothing for a filter that keeps all."""
    conditions = []
    for each in filters:
        if each.keep is None:
            continue
        name = quoted(each.field)
        parts = []
        listed = [literal(member) for member in each.keep if member is not None]
        if listed:
            parts.append(f"{name} IN ({', '.join(listed)})")
        if None in each.keep:
            parts.append(f"{name} IS NULL")
        conditions.append(parts[0] if len(parts) == 1 else "(" + " OR ".join(parts) + ")")
    return [f"{indent}WHERE " + " AND ".join(conditions)] if conditions else []


def member_query(definition: PivotDefinition) -> str:
    """The query for the members of the column field that are left after the filters, in their order."""
    field = definition.columns[0]
    lines = [f"SELECT DISTINCT {quoted(field)}", f"FROM {quoted(definition.source)}"]
    lines += where_lines(definition.filters)
    return "\n".join([*lines, f"ORDER BY {ordering(field)}"])


def data_columns(definition: PivotDefinition, members: Sequence[Value]) -> list[DataColumn]:
    """The columns of numbers a pivot has, in the order they are shown: each member's values, then the totals."""
    values = range(len(definition.values))
    if not definition.columns:
        return [DataColumn(Span.ALL, value) for value in values]
    columns = [DataColumn(Span.MEMBER, value, member) for member in members for value in values]
    if definition.total_column:
        columns += [DataColumn(Span.TOTAL, value) for value in values]
    return columns


def aliases(
    definition: PivotDefinition, columns: Sequence[DataColumn], titles: Sequence[str], labels: PivotLabels
) -> list[str]:
    """The names of the result's columns, the row labels' first, each different from the others."""
    first = definition.rows[0] if definition.rows else labels.row_header
    several = len(titles) > 1

    def name(column: DataColumn) -> str:
        if column.span is Span.ALL:
            return titles[column.value]
        base = (
            labels.total if column.span is Span.TOTAL else str(labels.blank if column.member is None else column.member)
        )
        return f"{base} · {titles[column.value]}" if several else base

    return column_names([first, *(name(column) for column in columns)])


def _expression(definition: PivotDefinition, column: DataColumn) -> str:
    value = definition.values[column.value]
    field = quoted(value.field)
    if column.span is Span.MEMBER:
        test = quoted(definition.columns[0])
        test += " IS NULL" if column.member is None else f" = {literal(column.member)}"
        field = f"CASE WHEN {test} THEN {field} END"
    return f"{value.aggregation.sql_function}({field})"


def _select(items: Sequence[str], prefix: str = "SELECT ") -> list[str]:
    pad = " " * len(prefix)
    return [
        (prefix if index == 0 else pad) + item + ("," if index < len(items) - 1 else "")
        for index, item in enumerate(items)
    ]


def pivot_query(
    definition: PivotDefinition, columns: Sequence[DataColumn], names: Sequence[str], labels: PivotLabels
) -> str:
    """The query that gives a pivot's rows: ``names`` are the result's column names (:func:`aliases`), the first
    for the row labels. Without a row field the one row is the total of everything."""
    expressions = [
        f"{_expression(definition, column)} AS {quoted(name)}" for column, name in zip(columns, names[1:], strict=True)
    ]
    source, where = quoted(definition.source), where_lines(definition.filters)
    if not definition.rows:
        return "\n".join(
            [*_select([f"{literal(labels.total)} AS {quoted(names[0])}", *expressions]), f"FROM {source}", *where]
        )
    field = quoted(definition.rows[0])
    group = f"GROUP BY {field}"
    if not definition.total_row:
        lines = [*_select([field, *expressions]), f"FROM {source}", *where, group]
        return "\n".join([*lines, f"ORDER BY {ordering(definition.rows[0])}"])
    order = "_order"
    while order in names:
        order += "_"
    total_items = ["1", literal(labels.total), *(_expression(definition, column) for column in columns)]
    outer = [quoted(name) for name in names]
    inner = [
        *_select([f"0 AS {quoted(order)}", field, *expressions], "  SELECT "),
        f"  FROM {source}",
        *where_lines(definition.filters, "  "),
        f"  {group}",
        "  UNION ALL",
        *_select(total_items, "  SELECT "),
        f"  FROM {source}",
        *where_lines(definition.filters, "  "),
    ]
    head = "SELECT " + ", ".join(outer)
    lines = [head] if len(head) <= _ONE_LINE else _select(outer)
    return "\n".join([*lines, "FROM (", *inner, ")", f"ORDER BY {quoted(order)}, {ordering(names[0])}"])
