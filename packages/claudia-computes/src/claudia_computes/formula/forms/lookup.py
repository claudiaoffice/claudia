"""Forms that find a value in a range: MATCH, XMATCH, XLOOKUP, VLOOKUP, HLOOKUP.

Looking up is what real models do most, so it is part of the core and made to stay fast. An exact search in a
column does not scan it: the first search builds an index of the column (value -> first position) which stays
until one of its cells changes, so a thousand lookups into the same table cost one pass over it, not a thousand.
Text is compared without regard to case. Wildcards (``*`` for any text, ``?`` for one character, ``~`` to escape)
work where Excel's do: ``MATCH``/``VLOOKUP``/``HLOOKUP`` for an exact search of text, and ``XLOOKUP``/``XMATCH``
with match mode 2.
"""

from __future__ import annotations

import re

from ...functions.range import Range
from ...values import NA, REF, VALUE, ErrorValue, FormulaError, Value
from ..compiler import Compiler, Evaluator
from ..nodes import Missing, Node
from ..operators import rank, single, sort_key
from . import form, truth, wrong_count
from .reference import result_of, whole_number

MAX_INDEXES = 256  # lookup indexes kept at a time
INDEX_FROM = 32  # a vector shorter than this is searched directly: an index would cost more than it saves
EXACT, SMALLER, LARGER, WILDCARD = 0, -1, 1, 2


def key_of(value: Value) -> object:
    """What two values must share to count as equal in a search (text without regard to case, TRUE apart from 1)."""
    if value.__class__ is bool:
        return ("b", value)
    return value.casefold() if value.__class__ is str else value


def _pattern(text: str) -> re.Pattern[str]:
    out, chars = [], iter(text)
    for char in chars:
        if char == "~":
            out.append(re.escape(next(chars, "~")))
        elif char == "*":
            out.append(".*")
        elif char == "?":
            out.append(".")
        else:
            out.append(re.escape(char))
    return re.compile("".join(out), re.IGNORECASE | re.DOTALL)


def _has_wildcard(value: Value) -> bool:
    return isinstance(value, str) and any(c in value for c in "*?~")


def _searchable(value: Value) -> bool:
    return value is not None and value.__class__ is not ErrorValue


def first_index(scope, vector: Range, values: list[Value], needle: Value) -> int | None:
    """Where ``needle`` first occurs, comparing exactly; an index of the vector is kept for long ones."""
    if len(values) < INDEX_FROM:
        wanted = key_of(needle)
        for position, value in enumerate(values):
            if _searchable(value) and key_of(value) == wanted:
                return position
        return None
    sheet = vector.sheet
    vertical = vector.n_cols == 1
    cache_key = (vector.sheet_id, vertical, vector.row0, vector.col0, vector.row1, vector.col1)
    version = sheet.column_version(vector.col0) if vertical else sheet.version()  # type: ignore[attr-defined]
    cached = scope.indexes.get(cache_key)
    if cached is None or cached[0] != version:
        built: dict[object, int] = {}
        for position, value in enumerate(values):
            if _searchable(value):
                built.setdefault(key_of(value), position)
        if len(scope.indexes) >= MAX_INDEXES:
            scope.indexes.clear()  # (an index is cheap to build again, and the memory they hold is bounded)
        scope.indexes[cache_key] = cached = (version, built)
    return cached[1].get(key_of(needle))


def find(scope, vector: Range, needle: Value, match: int, backwards: bool = False) -> int | None:
    """The position (from 0) in the vector of the match for ``needle``, or ``None``.

    ``match`` is EXACT, SMALLER (the exact value or else the largest smaller one), LARGER (the exact value or else
    the smallest larger one) or WILDCARD (exact, with ``*`` and ``?`` in text)."""
    if needle is None:
        return None
    values = vector.vector()
    if match == WILDCARD and _has_wildcard(needle):
        pattern = _pattern(needle)  # type: ignore[arg-type]
        order = range(len(values) - 1, -1, -1) if backwards else range(len(values))
        return next((i for i in order if isinstance(values[i], str) and pattern.fullmatch(values[i])), None)  # type: ignore[arg-type]
    if match in (EXACT, WILDCARD):
        if backwards:
            wanted = key_of(needle)
            return next(
                (i for i in range(len(values) - 1, -1, -1) if _searchable(values[i]) and key_of(values[i]) == wanted),
                None,
            )
        return first_index(scope, vector, values, needle)
    return _nearest(values, needle, smaller=match == SMALLER, backwards=backwards)


def _nearest(values: list[Value], needle: Value, *, smaller: bool, backwards: bool) -> int | None:
    """The exact value, or else the closest one below (``smaller``) or above, among values of the needle's kind."""
    kind, wanted = rank(needle), sort_key(needle)
    best: int | None = None
    order = range(len(values) - 1, -1, -1) if backwards else range(len(values))
    for position in order:
        value = values[position]
        if not _searchable(value) or rank(value) != kind:
            continue
        here = sort_key(value)
        if here == wanted:
            return position
        if (here < wanted) == smaller and (best is None or (sort_key(values[best]) < here) == smaller):
            best = position
    return best


def _sorted_search(values: list[Value], needle: Value, descending: bool) -> int | None:
    """MATCH with type 1 (ascending) or -1 (descending): the last position in sorted data that does not pass the
    needle."""
    kind, wanted = rank(needle), sort_key(needle)
    found: int | None = None
    for position, value in enumerate(values):
        if not _searchable(value) or rank(value) != kind:
            continue
        here = sort_key(value)
        if (here > wanted) if not descending else (here < wanted):
            break
        found = position
    return found


def _vector_arg(compiler: Compiler, node: Node):
    return compiler.compile_range(node)


@form("MATCH")
def match_form(compiler: Compiler, args: tuple[Node, ...]) -> Evaluator:
    """MATCH(value, range, type): the position (from 1) of the value in a row or column. Type 0 is an exact match
    (``*`` and ``?`` work in text); 1 (the default) finds the largest value that is not more than the given one in data
    sorted ascending; -1 the smallest that is not less, in data sorted descending. Not found is #N/A."""
    if not 2 <= len(args) <= 3:
        return wrong_count("MATCH", len(args), 2, 3)
    needle_arg, vector_arg = compiler.compile(args[0]), _vector_arg(compiler, args[1])
    type_arg = compiler.compile(args[2]) if len(args) == 3 else None

    def evaluate(scope):
        needle = single(needle_arg(scope))
        vector = vector_arg(scope)
        kind = 1 if type_arg is None else whole_number(type_arg(scope), "the match type")
        if kind == 0:
            position = find(scope, vector, needle, WILDCARD)
        else:
            position = None if needle is None else _sorted_search(vector.vector(), needle, descending=kind < 0)
        if position is None:
            raise FormulaError(NA, "the value was not found")
        return position + 1

    return evaluate


def _modes(match_arg, search_arg, scope) -> tuple[int, int]:
    match = EXACT if match_arg is None else whole_number(match_arg(scope), "the match mode")
    search = 1 if search_arg is None else whole_number(search_arg(scope), "the search mode")
    if match not in (EXACT, SMALLER, LARGER, WILDCARD):
        raise FormulaError(VALUE, "the match mode must be 0, -1, 1 or 2")
    if search not in (1, -1, 2, -2):
        raise FormulaError(VALUE, "the search mode must be 1, -1, 2 or -2")
    return match, search


def _position(scope, vector, needle, match: int, search: int) -> int | None:
    if search in (2, -2):  # binary search modes: the data is sorted, so the plain search finds the same thing
        search = 1
    return find(scope, vector, needle, match, backwards=search == -1)


@form("XMATCH")
def xmatch_form(compiler: Compiler, args: tuple[Node, ...]) -> Evaluator:
    """XMATCH(value, range, match mode, search mode): the position (from 1) of the value. Match mode 0 is exact, -1
    the exact value or else the next smaller, 1 or else the next larger, 2 exact with wildcards. Search mode 1 looks
    from the first, -1 from the last. Not found is #N/A."""
    if not 2 <= len(args) <= 4:
        return wrong_count("XMATCH", len(args), 2, 4)
    needle_arg, vector_arg = compiler.compile(args[0]), _vector_arg(compiler, args[1])
    match_arg = compiler.compile(args[2]) if len(args) > 2 else None
    search_arg = compiler.compile(args[3]) if len(args) > 3 else None

    def evaluate(scope):
        needle, vector = single(needle_arg(scope)), vector_arg(scope)
        match, search = _modes(match_arg, search_arg, scope)
        position = _position(scope, vector, needle, match, search)
        if position is None:
            raise FormulaError(NA, "the value was not found")
        return position + 1

    return evaluate


@form("XLOOKUP")
def xlookup_form(compiler: Compiler, args: tuple[Node, ...]) -> Evaluator:
    """XLOOKUP(value, lookup range, result range, if not found, match mode, search mode): the cell of the result range
    that lies beside the match in the lookup range. If nothing matches, ``if not found`` is evaluated and given (else
    #N/A). The modes are those of XMATCH. A result range with several columns (or rows) gives the whole row (or
    column)."""
    if not 3 <= len(args) <= 6:
        return wrong_count("XLOOKUP", len(args), 3, 6)
    needle_arg = compiler.compile(args[0])
    lookup_arg, result_arg = _vector_arg(compiler, args[1]), _vector_arg(compiler, args[2])
    fallback = compiler.compile(args[3]) if len(args) > 3 and not isinstance(args[3], Missing) else None
    match_arg = compiler.compile(args[4]) if len(args) > 4 else None
    search_arg = compiler.compile(args[5]) if len(args) > 5 else None

    def evaluate(scope):
        needle, vector, results = single(needle_arg(scope)), lookup_arg(scope), result_arg(scope)
        match, search = _modes(match_arg, search_arg, scope)
        if not vector.is_vector():
            raise FormulaError(VALUE, "XLOOKUP looks in a single row or a single column")
        down = vector.n_cols == 1
        if (results.n_rows if down else results.n_cols) != len(vector):
            raise FormulaError(VALUE, "the result range must be as long as the lookup range")
        position = _position(scope, vector, needle, match, search)
        if position is None:
            if fallback is None:
                raise FormulaError(NA, "the value was not found")
            return fallback(scope)
        return result_of(results.row(position) if down else results.column(position))

    return evaluate


def _table_lookup(name: str, by_rows: bool):
    @form(name)
    def make(compiler: Compiler, args: tuple[Node, ...]) -> Evaluator:
        if not 3 <= len(args) <= 4:
            return wrong_count(name, len(args), 3, 4)
        needle_arg, table_arg = compiler.compile(args[0]), _vector_arg(compiler, args[1])
        index_arg = compiler.compile(args[2])
        exact_arg = compiler.compile(args[3]) if len(args) == 4 else None

        def evaluate(scope):
            needle, table = single(needle_arg(scope)), table_arg(scope)
            index = whole_number(index_arg(scope), "the index")
            across = table.n_rows if by_rows else table.n_cols
            if index < 1:
                raise FormulaError(VALUE, f"{name} counts from 1")
            if index > across:
                raise FormulaError(REF, f"the table has only {across} {'rows' if by_rows else 'columns'}")
            approximate = True if exact_arg is None else truth(single(exact_arg(scope)))
            edge = table.row(0) if by_rows else table.column(0)
            values = edge.vector()
            if approximate:
                position = None if needle is None else _sorted_search(values, needle, descending=False)
            else:
                position = find(scope, edge, needle, WILDCARD)
            if position is None:
                raise FormulaError(NA, "the value was not found")
            return result_of(
                table.sub(index - 1, position, index - 1, position)
                if by_rows
                else table.sub(position, index - 1, position, index - 1)
            )

        return evaluate

    edge = "first row" if by_rows else "first column"
    make.__doc__ = f"{name}(value, table, index, exact): looks the value up in the {edge} of the table."
    return make


_table_lookup("VLOOKUP", by_rows=False)
_table_lookup("HLOOKUP", by_rows=True)
