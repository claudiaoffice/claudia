"""``SQL()``: a query over the tables of a workbook, on SQLite (E4.9, E6.5, D600).

Every evaluation opens a private in-memory database, which holds only the tables the query names: when SQLite says
``no such table: Sales`` the named range (or query result) of that name is copied in, with its header cells as column
names, and the query is run again. Nothing outlives the evaluation and nothing leaves it: an authorizer lets only
reading through (``SELECT``, the functions of SQLite but not the ones that make results differ between two
calculations or reach the machine), a progress handler stops a query after ``TIME_LIMIT`` seconds and a result is
refused beyond ``MAX_RESULT_ROWS`` rows. Everything a query is refused for is ``#SQL!`` with the reason in words.
"""

from __future__ import annotations

import re
import sqlite3
import time
from collections.abc import Callable, Sequence

from .names import Rect  # noqa: F401  (re-exported for callers that describe a result's place)
from .refs import column_name
from .spill import Table
from .values import SQL, ErrorValue, FormulaError, Value, fits_int, format_value

TIME_LIMIT = 1.0  # seconds a query may run
MAX_RESULT_ROWS = 100_000  # rows a result may have
_PROGRESS_STEPS = 2_000  # SQLite virtual machine instructions between two looks at the clock

_ALLOWED = frozenset({sqlite3.SQLITE_SELECT, sqlite3.SQLITE_READ, sqlite3.SQLITE_FUNCTION, sqlite3.SQLITE_RECURSIVE})
# functions whose answer differs from one calculation to the next, or that reach out of the database, or that can be
# made to allocate without bound
_DENIED_FUNCTIONS = frozenset({"random", "randomblob", "zeroblob", "load_extension", "readfile", "writefile"})
_MISSING = re.compile(r'no such table: (?:main\.)?"?([^"]+)"?$')

TableSource = Callable[[str], tuple[Sequence[str], Sequence[Sequence[Value]]] | None]


def column_names(headers: Sequence[str]) -> list[str]:
    """Names for columns from their header cells: a blank header is ``Column<n>``, a repeated one gets ``_2``,
    ``_3``... so that every column can be told apart in a query."""
    seen: dict[str, int] = {}
    names = []
    for index, header in enumerate(headers, start=1):
        text = header.strip() or f"Column{index}"
        count = seen.get(text.casefold(), 0) + 1
        seen[text.casefold()] = count
        names.append(text if count == 1 else f"{text}_{count}")
    return names


def column_type(values: Sequence[Value]) -> str:
    """``"int"``, ``"real"``, ``"text"``, or ``"mixed"`` (numbers and text together) for what a column holds."""
    kinds = {value.__class__ for value in values if value is not None and value.__class__ is not ErrorValue}
    if not kinds:
        return "text"
    if kinds <= {int, bool}:
        return "int"
    if kinds <= {int, bool, float}:
        return "real"
    return "text" if kinds == {str} else "mixed"


_DECLARED = {"int": "INTEGER", "real": "REAL", "text": "TEXT", "mixed": ""}  # ("" keeps what is stored as it is)


def quoted(name: str) -> str:
    """``name`` as an identifier in SQL."""
    return '"' + name.replace('"', '""') + '"'


def _stored(value: Value) -> int | float | str | None:
    if value is None or value.__class__ is ErrorValue:
        return None
    return int(value) if value.__class__ is bool else value  # type: ignore[return-value]


def _load(connection: sqlite3.Connection, table: str, headers: Sequence[str], rows: Sequence[Sequence[Value]]) -> None:
    names = column_names(headers)
    types = [column_type([row[i] for row in rows]) for i in range(len(names))]
    columns = ", ".join(f"{quoted(name)} {_DECLARED[kind]}".strip() for name, kind in zip(names, types, strict=True))
    connection.execute(f"CREATE TABLE {quoted(table)} ({columns})")
    marks = ", ".join("?" * len(names))
    connection.executemany(f"INSERT INTO {quoted(table)} VALUES ({marks})", ([_stored(v) for v in row] for row in rows))


def _value(item: object) -> Value:
    if item is None or isinstance(item, str):
        return item
    if isinstance(item, int):
        return item if fits_int(item) else float(item)
    if isinstance(item, float):
        return item
    return item.hex() if isinstance(item, bytes) else str(item)


def _explained(problem: sqlite3.Error) -> str:
    text = str(problem)
    if text == "interrupted":
        return f"the query ran for longer than {TIME_LIMIT:g} s and was stopped"
    return text[:1].lower() + text[1:] if text else "the query was refused"


def run_query(text: str, parameters: Sequence[object], tables: TableSource) -> Table:
    """The result of ``text`` over the tables ``tables`` can give (by name: the header texts and the rows of each, or
    ``None`` for a name that is none). Raises ``FormulaError`` with ``#SQL!`` for a query that is wrong, refused,
    too slow or gives too much."""
    connection = sqlite3.connect(":memory:")
    try:
        loading = [False]  # (while a table is being copied in, the authorizer allows what it needs)

        def authorize(action: int, first: str | None, second: str | None, *_: object) -> int:
            if loading[0]:
                return sqlite3.SQLITE_OK
            if action == sqlite3.SQLITE_FUNCTION:
                return sqlite3.SQLITE_DENY if (second or "").lower() in _DENIED_FUNCTIONS else sqlite3.SQLITE_OK
            return sqlite3.SQLITE_OK if action in _ALLOWED else sqlite3.SQLITE_DENY

        deadline = time.monotonic() + TIME_LIMIT
        connection.set_authorizer(authorize)
        connection.set_progress_handler(lambda: int(time.monotonic() > deadline), _PROGRESS_STEPS)
        loaded: set[str] = set()
        while True:
            try:
                cursor = connection.execute(text, tuple(parameters))
                found = cursor.fetchmany(MAX_RESULT_ROWS + 1)
                break
            except sqlite3.OperationalError as problem:
                missing = _MISSING.match(str(problem))
                data = tables(missing[1]) if missing is not None and missing[1].casefold() not in loaded else None
                if missing is None or data is None:
                    raise
                loaded.add(missing[1].casefold())
                loading[0] = True
                try:
                    _load(connection, missing[1], *data)
                finally:
                    loading[0] = False
        columns = tuple(item[0] for item in cursor.description or ())
        if not columns:
            raise FormulaError(SQL, "the query gave no columns: use SELECT")
        if len(found) > MAX_RESULT_ROWS:
            raise FormulaError(SQL, f"the result has more than {MAX_RESULT_ROWS:,} rows: filter it or add a LIMIT")
        return Table(columns, tuple(tuple(_value(item) for item in row) for row in found))
    except sqlite3.Error as problem:
        raise FormulaError(SQL, _explained(problem)) from None
    finally:
        connection.close()


def parameter(value: object) -> object:
    """A cell value as something SQLite binds."""
    if isinstance(value, bool):
        return int(value)
    if value is None or isinstance(value, (int, float, str)):
        return value
    return format_value(value)  # type: ignore[arg-type]


__all__ = ["MAX_RESULT_ROWS", "TIME_LIMIT", "Table", "column_name", "column_names", "column_type", "run_query"]
