"""A pivot table made into a grid of values (E6.30, D621, D622).

:func:`compute_pivot` reads a definition's fields off its source, asks the SQL engine for the column members and then
for the numbers (:mod:`.pivot_sql`), and lays the answer out as Excel's compact pivot table does: the field names
and the column members as headers, one row per row member, and the totals last. The grid is plain values, each
cell with the *role* it plays (:class:`PivotRole`), so that how a header or a total looks is a matter of styles
(D604), not of this module. Where the grid is put, what owns its cells and how it follows the source is the
model's business and comes later.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, replace
from enum import StrEnum

from claudia_core import N_

from . import sql as engine
from .pivot import DEFAULT_LABELS, PivotDefinition, PivotError, PivotLabels
from .pivot_sql import DataColumn, Span, aliases, data_columns, member_query, pivot_query
from .spill import Matrix, Table
from .values import FormulaError, Value

#: The most columns of numbers a pivot may have: SQLite's own limit is 2000 columns in a result.
MAX_DATA_COLUMNS = 1_000


class PivotRole(StrEnum):
    """What a cell of a pivot is for, so a style can follow it: the ``CORNER`` that names the value (when there is
    one), a ``FIELD`` name (Region, Quarter), a ``HEADER`` (a column member, a value's title, or a blank one that
    belongs to the header), a row ``LABEL``, a ``VALUE``, and a ``TOTAL`` (a total row or column, and its label)."""

    CORNER = "corner"
    FIELD = "field"
    HEADER = "header"
    LABEL = "label"
    VALUE = "value"
    TOTAL = "total"


@dataclass(frozen=True, slots=True)
class PivotResult:
    """A pivot's grid: the ``header_rows`` first, then a row for each member of the row field and the total row.
    ``sql`` is the query the numbers came from (empty when nothing is chosen yet). Like a
    :class:`~claudia_computes.spill.Table` it is something a formula or an object can fill cells with."""

    rows: tuple[tuple[Value, ...], ...]
    roles: tuple[tuple[PivotRole, ...], ...]
    header_rows: int
    sql: str
    total_column: bool = False

    @property
    def total_row(self) -> bool:
        """Whether the last row is a total (a pivot with no row field is that one row)."""
        return self.height > self.header_rows and self.roles[-1][0] is PivotRole.TOTAL

    @property
    def height(self) -> int:
        """Rows it takes up on a sheet."""
        return len(self.rows)

    @property
    def width(self) -> int:
        """Columns it takes up on a sheet."""
        return len(self.rows[0]) if self.rows else 0

    def value_at(self, row: int, col: int) -> Value:
        """The value in the cell ``row`` rows down and ``col`` columns right of the top left corner."""
        return self.rows[row][col]

    def role_at(self, row: int, col: int) -> PivotRole:
        """What the cell at ``row``, ``col`` is for."""
        return self.roles[row][col]

    def as_matrix(self) -> Matrix:
        """The values as a rectangle with no roles; raises ``ValueError`` when nothing is chosen yet."""
        return Matrix(self.rows)


def compute_pivot(
    definition: PivotDefinition, tables: engine.TableSource, labels: PivotLabels = DEFAULT_LABELS
) -> PivotResult:
    """The pivot table ``definition`` makes of the table or range its source names, as ``tables`` gives it (the
    header texts and the rows of a name, or ``None`` for one that is none: the engine's own ``TableSource``).

    Raises :class:`PivotError` for a source or a field the source does not have, two value fields with one title, a
    pivot with too many columns, and whatever the engine refuses a query for (D605). A definition with no value
    field gives an empty result: there is nothing to add up yet."""
    data = tables(definition.source)
    if data is None:
        raise PivotError(N_("no table or range named {source!r}"), source=definition.source)
    resolved = _resolved(definition, engine.column_names(data[0]))
    if not resolved.values:
        return PivotResult((), (), 0, "")
    titles = _titles(resolved, labels)
    members = [row[0] for row in _run(member_query(resolved), tables).rows] if resolved.columns else []
    columns = data_columns(resolved, members)
    if len(columns) > MAX_DATA_COLUMNS:
        raise PivotError(
            N_(
                "the pivot would have {count:,} columns, at most {limit:,} fit: {field!r} has too many members for "
                "the columns"
            ),
            count=len(columns),
            limit=MAX_DATA_COLUMNS,
            field=resolved.columns[0],
        )
    names = aliases(resolved, columns, titles, labels)
    query = pivot_query(resolved, columns, names, labels)
    return _lay_out(resolved, columns, titles, _run(query, tables), labels, query)


def _run(query: str, tables: engine.TableSource) -> Table:
    try:
        return engine.run_query(query, (), tables)
    except FormulaError as problem:
        raise PivotError(problem.detail or problem.code) from None


def _resolved(definition: PivotDefinition, names: Sequence[str]) -> PivotDefinition:
    """``definition`` with every field written as the source writes it, or ``PivotError`` for one it does not have."""
    known = {name.casefold(): name for name in names}

    def find(field: str) -> str:
        if field.casefold() not in known:
            raise PivotError(
                N_("no field {field!r} in {source}: {names}"),
                field=field,
                source=definition.source,
                names=", ".join(names),
            )
        return known[field.casefold()]

    return replace(
        definition,
        rows=tuple(find(field) for field in definition.rows),
        columns=tuple(find(field) for field in definition.columns),
        values=tuple(replace(value, field=find(value.field)) for value in definition.values),
        filters=tuple(replace(each, field=find(each.field)) for each in definition.filters),
    )


def _titles(definition: PivotDefinition, labels: PivotLabels) -> list[str]:
    titles = [value.name or labels.title(value.aggregation, value.field) for value in definition.values]
    for index, title in enumerate(titles):
        if title.casefold() in (other.casefold() for other in titles[:index]):
            raise PivotError(
                N_("two value fields are both called {title!r}: give one of them another name"), title=title
            )
    return titles


def _lay_out(
    definition: PivotDefinition,
    columns: Sequence[DataColumn],
    titles: Sequence[str],
    table: Table,
    labels: PivotLabels,
    query: str,
) -> PivotResult:
    headers = _headers(definition, columns, titles, labels)
    rows = [cells for cells, _ in headers]
    roles = [kinds for _, kinds in headers]
    last = len(table.rows) - 1
    for index, row in enumerate(table.rows):
        total_row = not definition.rows or (definition.total_row and index == last)
        label = row[0] if total_row else (labels.blank if row[0] is None else row[0])
        rows.append((label, *row[1:]))
        roles.append(
            (
                PivotRole.TOTAL if total_row else PivotRole.LABEL,
                *(PivotRole.TOTAL if total_row or column.span is Span.TOTAL else PivotRole.VALUE for column in columns),
            )
        )
    total_column = any(column.span is Span.TOTAL for column in columns)
    return PivotResult(tuple(rows), tuple(roles), len(headers), query, total_column)


def _headers(
    definition: PivotDefinition, columns: Sequence[DataColumn], titles: Sequence[str], labels: PivotLabels
) -> list[tuple[tuple[Value, ...], tuple[PivotRole, ...]]]:
    """The header rows with their roles: one without a column field, two for one value under it, three for several."""
    width = 1 + len(columns)
    corner = definition.rows[0] if definition.rows else None
    corner_role = PivotRole.FIELD if definition.rows else PivotRole.HEADER

    def row(cells: Sequence[Value], roles: Sequence[PivotRole]) -> tuple[tuple[Value, ...], tuple[PivotRole, ...]]:
        return tuple([*cells, *([None] * width)][:width]), tuple(roles[:width])

    headed = [PivotRole.HEADER] * width
    value_titles = [titles[column.value] for column in columns]
    if not definition.columns:
        return [row([corner, *value_titles], [corner_role, *headed[1:]])]
    several = len(titles) > 1
    members = [
        None if column.value else (labels.total if column.span is Span.TOTAL else _member(column.member, labels))
        for column in columns
    ]
    if not several:
        return [
            row([titles[0], definition.columns[0]], [PivotRole.CORNER, PivotRole.FIELD, *headed]),
            row([corner, *members], [corner_role, *headed[1:]]),
        ]
    return [
        row([None, definition.columns[0]], [PivotRole.HEADER, PivotRole.FIELD, *headed]),
        row([None, *members], headed),
        row([corner, *value_titles], [corner_role, *headed[1:]]),
    ]


def _member(member: Value, labels: PivotLabels) -> Value:
    return labels.blank if member is None else member
