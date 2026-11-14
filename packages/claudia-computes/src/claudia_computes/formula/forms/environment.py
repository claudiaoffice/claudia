"""Forms about the document and the moment: TODAY, NOW, SHEET, SHEETS, CELL, INFO, ISFORMULA, ISREF, FORMULATEXT,
AREAS, TYPE, N, T, ERROR.TYPE and LET.

TODAY and NOW read ``scope.clock``. They are calculated when their cell is calculated (opening the document, editing
what they depend on, Resample), not by a timer: a cell with ``=NOW()`` does not tick."""

from __future__ import annotations

from ...functions.range import Range
from ...refs import column_name
from ...spill import Matrix
from ...values import NA, VALUE, ErrorValue, FormulaError
from ..compiler import Compiler, Evaluator
from ..nodes import Area, Node, Paren, Ref
from ..operators import single
from . import form, wrong_count

_SECONDS_A_DAY = 86400


@form("TODAY")
def today(compiler: Compiler, args: tuple[Node, ...]) -> Evaluator:
    """TODAY(): today's date as a day number (the time of day is left out)."""
    from ...functions.library.dates import serial_of

    if args:
        return wrong_count("TODAY", len(args), 0, 0)

    def evaluate(scope):
        return serial_of(scope.clock().date())

    return evaluate


@form("NOW")
def now(compiler: Compiler, args: tuple[Node, ...]) -> Evaluator:
    """NOW(): the date and time as a day number with the time of day as its fraction."""
    from ...functions.library.dates import serial_of

    if args:
        return wrong_count("NOW", len(args), 0, 0)

    def evaluate(scope):
        moment = scope.clock()
        seconds = moment.hour * 3600 + moment.minute * 60 + moment.second + moment.microsecond / 1e6
        return serial_of(moment.date()) + seconds / _SECONDS_A_DAY

    return evaluate


def _is_reference(node: Node) -> bool:
    while isinstance(node, Paren):
        node = node.inner
    return isinstance(node, (Ref, Area))


@form("ISREF")
def isref(compiler: Compiler, args: tuple[Node, ...]) -> Evaluator:
    """ISREF(value): TRUE if the value is a reference to cells (A1, A1:B2, or what OFFSET or INDIRECT give)."""
    if len(args) != 1:
        return wrong_count("ISREF", len(args), 1, 1)
    if _is_reference(args[0]):
        return lambda scope: True
    inner = compiler.compile(args[0])

    def evaluate(scope):
        try:
            value = inner(scope)
        except FormulaError:
            return False
        return value.__class__ is Range and value.sheet_id is not None

    return evaluate


@form("ISFORMULA")
def isformula(compiler: Compiler, args: tuple[Node, ...]) -> Evaluator:
    """ISFORMULA(reference): TRUE if the cell holds a formula."""
    if len(args) != 1:
        return wrong_count("ISFORMULA", len(args), 1, 1)
    target = compiler.compile_range(args[0])

    def evaluate(scope):
        area = target(scope)
        return scope.formula_of(area.sheet_id, (area.row0, area.col0)) is not None

    return evaluate


@form("FORMULATEXT")
def formulatext(compiler: Compiler, args: tuple[Node, ...]) -> Evaluator:
    """FORMULATEXT(reference): the formula in the cell as text, or #N/A if the cell holds none."""
    if len(args) != 1:
        return wrong_count("FORMULATEXT", len(args), 1, 1)
    target = compiler.compile_range(args[0])

    def evaluate(scope):
        area = target(scope)
        text = scope.formula_of(area.sheet_id, (area.row0, area.col0))
        if text is None:
            raise FormulaError(NA, "the cell holds no formula")
        return text

    return evaluate


@form("AREAS")
def areas(compiler: Compiler, args: tuple[Node, ...]) -> Evaluator:
    """AREAS(reference): how many areas the reference has. A reference is one area: claudia has no unions."""
    if len(args) != 1:
        return wrong_count("AREAS", len(args), 1, 1)
    target = compiler.compile_range(args[0])

    def evaluate(scope):
        target(scope)
        return 1

    return evaluate


def _sheet_number(scope, sheet_id) -> int:
    return list(scope.sheets).index(sheet_id) + 1


@form("SHEET")
def sheet(compiler: Compiler, args: tuple[Node, ...]) -> Evaluator:
    """SHEET([reference or name]): the number of the sheet (counting from 1) the reference or the named sheet is on;
    of this sheet without an argument."""
    if len(args) > 1:
        return wrong_count("SHEET", len(args), 0, 1)
    if not args:
        return lambda scope: _sheet_number(scope, scope.home)
    if _is_reference(args[0]):
        target = compiler.compile_range(args[0])
        return lambda scope: _sheet_number(scope, target(scope).sheet_id or scope.home)
    inner = compiler.compile(args[0])

    def evaluate(scope):
        name = single(inner(scope))
        found = scope.sheet_id(name) if isinstance(name, str) else None
        if found is None:
            raise FormulaError(NA, "there is no such sheet")
        return _sheet_number(scope, found)

    return evaluate


@form("SHEETS")
def sheets(compiler: Compiler, args: tuple[Node, ...]) -> Evaluator:
    """SHEETS([reference]): how many sheets the workbook has (1 for a reference)."""
    if len(args) > 1:
        return wrong_count("SHEETS", len(args), 0, 1)
    if args:
        return lambda scope: 1
    return lambda scope: len(scope.sheets)


def _type_of(value: object) -> int:
    if value.__class__ in (Range, Matrix):
        cells = value.height * value.width if value.__class__ is Matrix else len(value)  # type: ignore[arg-type]
        return 64 if cells != 1 else _type_of(single(value))
    if value.__class__ is ErrorValue:
        return 16
    if value.__class__ is bool:
        return 4
    return 2 if value.__class__ is str else 1


@form("TYPE")
def type_(compiler: Compiler, args: tuple[Node, ...]) -> Evaluator:
    """TYPE(value): 1 for a number (and an empty cell), 2 for text, 4 for TRUE/FALSE, 16 for an error, 64 for several
    values."""
    if len(args) != 1:
        return wrong_count("TYPE", len(args), 1, 1)
    inner = compiler.compile_range(args[0]) if _is_reference(args[0]) else compiler.compile(args[0])

    def evaluate(scope):
        try:
            value = inner(scope)
            if value.__class__ is Range and len(value) == 1:
                value = value.at(0, 0)
        except FormulaError:
            return 16
        return _type_of(value)

    return evaluate


@form("N")
def n(compiler: Compiler, args: tuple[Node, ...]) -> Evaluator:
    """N(value): a number as it is, TRUE as 1, FALSE as 0, a date as its number, anything else (text, empty) as 0."""
    if len(args) != 1:
        return wrong_count("N", len(args), 1, 1)
    inner = compiler.compile(args[0])

    def evaluate(scope):
        value = single(inner(scope))
        if value.__class__ is bool:
            return int(value)
        return value if value.__class__ in (int, float) else 0

    return evaluate


@form("T")
def t(compiler: Compiler, args: tuple[Node, ...]) -> Evaluator:
    """T(value): the text if the value is text, otherwise empty text."""
    if len(args) != 1:
        return wrong_count("T", len(args), 1, 1)
    inner = compiler.compile(args[0])

    def evaluate(scope):
        value = single(inner(scope))
        return value if value.__class__ is str else ""

    return evaluate


_ERROR_NUMBERS = {"#NULL!": 1, "#DIV/0!": 2, "#VALUE!": 3, "#REF!": 4, "#NAME?": 5, "#NUM!": 6, "#N/A": 7}


@form("ERROR.TYPE")
def error_type(compiler: Compiler, args: tuple[Node, ...]) -> Evaluator:
    """ERROR.TYPE(value): 1 #NULL!, 2 #DIV/0!, 3 #VALUE!, 4 #REF!, 5 #NAME?, 6 #NUM!, 7 #N/A; #N/A if there is no error."""
    if len(args) != 1:
        return wrong_count("ERROR.TYPE", len(args), 1, 1)
    inner = compiler.compile(args[0])

    def evaluate(scope):
        try:
            value = single(inner(scope))
        except FormulaError as problem:
            number = _ERROR_NUMBERS.get(problem.code)
        else:
            number = _ERROR_NUMBERS.get(value.code) if value.__class__ is ErrorValue else None
        if number is None:
            raise FormulaError(NA, "there is no error")
        return number

    return evaluate


_INFO_CELL = {"format": "G", "prefix": "", "protect": 0, "parentheses": 0, "color": 0, "filename": ""}


@form("CELL")
def cell(compiler: Compiler, args: tuple[Node, ...]) -> Evaluator:
    """CELL(info, [reference]): "address" ($A$1), "row", "col", "contents", "type" (b blank, l text, v other), "sheet",
    and the plain defaults "format" (G), "prefix", "protect", "parentheses", "color" and "filename". Others
    ("width") are #N/A: claudia has no column widths a formula can see."""
    if not 1 <= len(args) <= 2:
        return wrong_count("CELL", len(args), 1, 2)
    what = compiler.compile(args[0])
    target = compiler.compile_range(args[1]) if len(args) == 2 else None

    def evaluate(scope):
        kind = single(what(scope))
        if not isinstance(kind, str):
            raise FormulaError(VALUE, "the first argument names the information, in quotes")
        kind = kind.strip().lower()
        area = target(scope) if target else Range(scope.sheets[scope.home], scope.row, scope.col, scope.row, scope.col, sheet_id=scope.home)
        row, col = area.row0, area.col0
        if kind == "address":
            return f"${column_name(col)}${row + 1}"
        if kind == "row":
            return row + 1
        if kind == "col":
            return col + 1
        if kind == "sheet":
            return _sheet_number(scope, area.sheet_id or scope.home)
        if kind in ("contents", "type"):
            value = area.at(0, 0)
            if value.__class__ is ErrorValue and kind == "contents":
                raise value.raised()
            if kind == "contents":
                return value
            return "b" if value is None else "l" if isinstance(value, str) else "v"
        if kind in _INFO_CELL:
            return _INFO_CELL[kind]
        raise FormulaError(NA, f"claudia cannot tell {kind!r} of a cell")

    return evaluate


@form("INFO")
def info(compiler: Compiler, args: tuple[Node, ...]) -> Evaluator:
    """INFO(type): "recalc" (Automatic), "numfile" (the number of sheets), "origin" ($A:$A$1), "system" (claudia) and
    "release" (the version of the formula language). Others are #N/A."""
    if len(args) != 1:
        return wrong_count("INFO", len(args), 1, 1)
    what = compiler.compile(args[0])

    def evaluate(scope):
        kind = single(what(scope))
        kind = kind.strip().lower() if isinstance(kind, str) else None
        if kind == "recalc":
            return "Automatic"
        if kind == "numfile":
            return len(scope.sheets)
        if kind == "origin":
            return "$A:$A$1"
        if kind == "system":
            return "claudia"
        raise FormulaError(NA, "claudia does not know that")

    return evaluate


@form("LET")
def let(compiler: Compiler, args: tuple[Node, ...]) -> Evaluator:
    """LET(name1, value1, [name2, value2, ...], calculation): give names to values (later ones may use earlier ones)
    and calculate with them."""
    from ..nodes import Name

    if len(args) < 3 or len(args) % 2 == 0:
        return wrong_count("LET", len(args), 3, None)
    bound: list[tuple[str, Evaluator]] = []
    added: list[str] = []
    try:
        for name_node, value_node in zip(args[0:-1:2], args[1:-1:2], strict=True):
            if not isinstance(name_node, Name):
                raise FormulaError(VALUE, "LET names its values with plain names")
            key = name_node.text.casefold()
            bound.append((key, compiler.compile(value_node)))  # (a value cannot use its own name yet)
            if key not in compiler.local_names:
                compiler.local_names.add(key)
                added.append(key)
        body = compiler.compile(args[-1])
    except FormulaError as problem:
        return failing_with(problem)
    finally:
        compiler.local_names.difference_update(added)

    def evaluate(scope):
        saved = {key: scope.variables[key] for key, _ in bound if key in scope.variables}
        try:
            for key, value in bound:
                scope.variables[key] = value(scope)
            return body(scope)
        finally:
            for key, _ in bound:
                scope.variables.pop(key, None)
            scope.variables.update(saved)

    return evaluate


def failing_with(problem: FormulaError) -> Evaluator:
    from ..compiler import failing

    return failing(problem.code, problem.detail)
