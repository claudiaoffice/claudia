"""Reading formula text.

Two steps, both made to be fast because every typed formula, every undo and every reopened document goes through
them: one compiled regular expression cuts the text into tokens in a single pass, and a precedence-climbing parser
(one loop for all binary operators, not one method per level) builds the tree. References are recognised by the
tokenizer itself and the references a formula reads are collected while it is parsed, so nobody walks the tree again
to find them.

Syntax (modelled on Excel)::

    literals     1  2.5  1e3  "text"  TRUE  FALSE  #N/A
    references   A1  $B$2  Sheet2!A1  'My Sheet'!A1:B3  A:C  2:4
    names        rate                      (a word that is neither a function nor a cell)
    operators    ^   *  /   +  -   &   = <> < > <= >=   and the postfix %   (loosest last)
    functions    SUM(A1:A3, 2)  IF(A1,,2)  (an argument may be left out)

``-`` binds tighter than ``^`` (``-2^2`` is 4) and ``^`` groups from the left, as in Excel.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass

from ..limits import MAX_COLS, MAX_ROWS
from ..refs import CellRef, RangeRef, SheetId, column_index
from ..values import ERROR_CODES, REF, SYNTAX, ErrorValue, fits_int
from .nodes import (
    Area,
    BadRef,
    Binary,
    Bool,
    Call,
    ErrorLit,
    Missing,
    Name,
    Node,
    Num,
    Paren,
    Percent,
    Ref,
    Str,
    Unary,
)

MAX_LENGTH = 8192  # characters, like Excel
MAX_DEPTH = 64  # nested brackets and signs, like Excel's nesting of functions
DYNAMIC_FUNCTIONS = frozenset({"OFFSET", "INDIRECT"})  # read cells that the text alone does not name

SheetIds = Callable[[str], SheetId | None]

_SHEET = r"(?:'(?:[^']|'')+'|[A-Za-z_][A-Za-z0-9_.]*)!"
_TOKEN = re.compile(
    rf"""
    \s*(?:
        (?P<ref>(?P<rs>{_SHEET})?(?P<ca>\$?)(?P<cl>[A-Za-z]{{1,3}})(?P<ra>\$?)(?P<rw>[0-9]+))(?![A-Za-z0-9_(])
      | (?P<str>"(?:[^"]|"")*")
      | (?P<rows>(?:{_SHEET})?\$?[0-9]+:\$?[0-9]+)(?![A-Za-z0-9_(.])
      | (?P<num>(?:[0-9]+\.?[0-9]*|\.[0-9]+)(?:[eE][+-]?[0-9]+)?)
      | (?P<op><>|<=|>=|[-+*/^&%(),:=<>])
      | (?P<cols>(?:{_SHEET})?\$?[A-Za-z]{{1,3}}:\$?[A-Za-z]{{1,3}})(?![A-Za-z0-9_(])
      | (?P<func>[A-Za-z_][A-Za-z0-9_.]*)(?=\s*\()
      | (?P<ident>[A-Za-z_][A-Za-z0-9_.]*)
      | (?P<err>\#(?:REF!|DIV/0!|VALUE!|NAME\?|NUM!|N/A|NULL!))
      | (?P<junk>.)
    )
    """,
    re.VERBOSE | re.DOTALL,
)
_COLUMN = re.compile(r"(\$?)([A-Za-z]{1,3})")
_ROW = re.compile(r"(\$?)([0-9]+)")

# binding power of each binary operator; the postfix % and the prefix signs bind tighter than any of them
_BINDING = {
    "=": 10,
    "<>": 10,
    "<": 10,
    ">": 10,
    "<=": 10,
    ">=": 10,
    "&": 20,
    "+": 30,
    "-": 30,
    "*": 40,
    "/": 40,
    "^": 50,
}
_PERCENT = 60
_PREFIX = 70

_column_cache: dict[str, int] = {}


class _Syntax(Exception):
    """Internal: the text is not a formula; the message says what stopped the reading."""


@dataclass(frozen=True, slots=True)
class Formula:
    """A formula read from text. ``ast`` is ``None`` when the text could not be read; ``error`` then says why and
    ``source`` still holds the text as typed, so the person can see and fix it.

    ``refs`` is every cell or range the formula names (a cell as a range of one), in the order of the text and
    without repeats; ``sheet`` is ``None`` for the sheet the formula is on. ``dynamic`` is true when it also reads
    cells that its text does not name (``OFFSET``, ``INDIRECT``)."""

    source: str
    ast: Node | None
    error: ErrorValue | None = None
    refs: tuple[RangeRef, ...] = ()
    dynamic: bool = False


def parse_formula(text: str, sheet_ids: SheetIds | None = None) -> Formula:
    """Read ``text`` (with its leading ``=``). Never raises. ``sheet_ids`` turns a sheet's name into its id."""
    source = text.strip()
    body = source[1:] if source.startswith("=") else source
    try:
        if len(source) > MAX_LENGTH:
            raise _Syntax(f"a formula may have at most {MAX_LENGTH} characters")
        parser = _Parser(_tokens(body), sheet_ids)
        node = parser.parse()
    except _Syntax as problem:
        return Formula(source, None, ErrorValue(SYNTAX, str(problem)))
    except RecursionError:
        return Formula(source, None, ErrorValue(SYNTAX, "the formula is nested too deeply"))
    return Formula(source, node, None, tuple(dict.fromkeys(parser.refs)), parser.dynamic)


# ------------------------------------------------------------------------------------ tokens
Token = tuple[str, str, tuple[str | None, ...] | None]  # (kind, text, the parts of a cell reference)


def _tokens(text: str) -> list[Token]:
    tokens: list[Token] = []
    for found in _TOKEN.finditer(text.strip()):
        kind = found.lastgroup or ""
        if kind == "ref":
            tokens.append((kind, found[kind], found.group("rs", "ca", "cl", "ra", "rw")))
        elif kind == "junk":
            raise _Syntax(f"unexpected {found[kind]!r}")
        else:
            tokens.append((kind, found[kind], None))
    return tokens


def _number(text: str) -> int | float:
    """A number as typed: plain digits are a whole number while it is exact, anything else a float."""
    if text.isdigit() and len(text) <= 25 and fits_int(whole := int(text)):
        return whole
    return float(text)


def _cell(parts: tuple[str | None, ...], sheet: SheetId | None) -> CellRef | None:
    """The cell named by the parts of a reference token, or ``None`` when it lies outside the sheet (then it is
    only a name)."""
    _, col_abs, letters, row_abs, digits = parts
    col, row = _column(letters or ""), int(digits or "0") - 1
    if not (0 <= row < MAX_ROWS and 0 <= col < MAX_COLS):
        return None
    return CellRef(row, col, sheet, bool(row_abs), bool(col_abs))


def _column(letters: str) -> int:
    index = _column_cache.get(letters)
    if index is None:
        index = _column_cache[letters] = column_index(letters)
    return index


# ------------------------------------------------------------------------------------ parser
class _Parser:
    def __init__(self, tokens: list[Token], sheet_ids: SheetIds | None):
        self.tokens = tokens
        self.sheet_ids = sheet_ids
        self.at = 0
        self.depth = 0
        self.refs: list[RangeRef] = []
        self.dynamic = False

    def parse(self) -> Node:
        if not self.tokens:
            raise _Syntax("the formula is empty")
        node = self.expression(0)
        if self.at != len(self.tokens):
            raise _Syntax(f"unexpected {self.tokens[self.at][1]!r}")
        return node

    # -- expressions
    def expression(self, floor: int) -> Node:
        """An expression whose operators bind at least as tight as ``floor``."""
        self.depth += 1
        if self.depth > MAX_DEPTH:
            raise _Syntax(f"brackets are nested more than {MAX_DEPTH} deep")
        left = self.prefix()
        tokens = self.tokens
        while self.at < len(tokens):
            kind, text, _ = tokens[self.at]
            if kind != "op":
                break
            if text == "%":
                if floor > _PERCENT:
                    break
                self.at += 1
                left = Percent(left)
                continue
            binding = _BINDING.get(text)
            if binding is None or binding < floor:
                break
            self.at += 1
            left = Binary(text, left, self.expression(binding + 1))  # (+1: operators of one level group from the left)
        self.depth -= 1
        return left

    def take(self) -> Token:
        if self.at >= len(self.tokens):
            raise _Syntax("the formula ends too early")
        token = self.tokens[self.at]
        self.at += 1
        return token

    def accept(self, op: str) -> bool:
        if self.at < len(self.tokens) and self.tokens[self.at][:2] == ("op", op):
            self.at += 1
            return True
        return False

    def prefix(self) -> Node:
        kind, text, parts = self.take()
        match kind:
            case "num":
                return Num(_number(text), text)
            case "str":
                return Str(text[1:-1].replace('""', '"'))
            case "err":
                return BadRef() if text == REF else ErrorLit(text if text in ERROR_CODES else SYNTAX)
            case "ref":
                return self.reference(parts or ())
            case "cols":
                return self.whole(text, columns=True)
            case "rows":
                return self.whole(text, columns=False)
            case "func":
                return self.call(text)
            case "ident":
                upper = text.upper()
                return Bool(upper == "TRUE") if upper in ("TRUE", "FALSE") else Name(text)
            case "op" if text in ("-", "+"):
                return Unary(text, self.expression(_PREFIX))
            case "op" if text == "(":
                inner = self.expression(0)
                if not self.accept(")"):
                    raise _Syntax("a bracket is not closed")
                return Paren(inner)
        raise _Syntax(f"unexpected {text!r}")

    def call(self, name: str) -> Node:
        if not self.accept("("):  # (the tokenizer only says "func" when a bracket follows)
            raise _Syntax(f"{name} needs a bracket")
        args: list[Node] = []
        if self.accept(")"):
            return self.finish_call(name, args)
        while True:
            if self.at < len(self.tokens) and self.tokens[self.at][0] == "op" and self.tokens[self.at][1] in ",)":
                args.append(Missing())
            else:
                args.append(self.expression(0))
            if self.accept(","):
                continue
            if self.accept(")"):
                return self.finish_call(name, args)
            raise _Syntax(f"{name}( is not closed")

    def finish_call(self, name: str, args: list[Node]) -> Node:
        upper = name.upper()
        if upper in DYNAMIC_FUNCTIONS:
            self.dynamic = True
        return Call(upper, tuple(args))

    # -- references
    def sheet_of(self, prefix: str | None) -> tuple[SheetId | None, bool]:
        """(sheet id, whether the sheet is known) for the ``Sheet!`` in front of a reference, if there is one."""
        if prefix is None:
            return None, True
        name = prefix[:-1]
        if name.startswith("'"):
            name = name[1:-1].replace("''", "'")
        sheet = self.sheet_ids(name) if self.sheet_ids else None
        return sheet, sheet is not None

    def reference(self, parts: tuple[str | None, ...]) -> Node:
        sheet, known = self.sheet_of(parts[0])
        first = _cell(parts, sheet)
        if first is None:
            return Name("".join(p or "" for p in parts))
        tokens = self.tokens
        if self.at + 1 < len(tokens) and tokens[self.at][:2] == ("op", ":") and tokens[self.at + 1][0] == "ref":
            other_parts = tokens[self.at + 1][2] or ()
            self.at += 2
            other_sheet, other_known = self.sheet_of(other_parts[0])
            second = _cell(other_parts, sheet)
            if second is None:
                raise _Syntax(f"{''.join(p or '' for p in other_parts)!r} is not a cell")
            if not known or not other_known or (other_sheet is not None and other_sheet != sheet):
                return BadRef()  # (an unknown sheet, or a range from one sheet to another)
            in_order = first.row <= second.row and first.col <= second.col
            area = RangeRef(first, second) if in_order else RangeRef.between(first, second)
            self.refs.append(area)
            return Area(area)
        if not known:
            return BadRef()
        self.refs.append(RangeRef(first, first))
        return Ref(first)

    def whole(self, token: str, *, columns: bool) -> Node:
        """``A:C`` (whole columns) or ``2:4`` (whole rows)."""
        prefix, bang, rest = token.rpartition("!")
        sheet, known = self.sheet_of(prefix + bang or None)
        left, _, right = rest.partition(":")
        pattern = _COLUMN if columns else _ROW
        a, b = pattern.fullmatch(left), pattern.fullmatch(right)
        if a is None or b is None:
            raise _Syntax(f"{token!r} is not a range")
        if columns:
            c1, c2 = _column(a[2]), _column(b[2])
            if max(c1, c2) >= MAX_COLS:
                return Name(token)
            area = RangeRef.between(
                CellRef(0, c1, sheet, False, bool(a[1])), CellRef(MAX_ROWS - 1, c2, sheet, False, bool(b[1]))
            )
        else:
            r1, r2 = int(a[2]) - 1, int(b[2]) - 1
            if min(r1, r2) < 0 or max(r1, r2) >= MAX_ROWS:
                return Name(token)
            area = RangeRef.between(
                CellRef(r1, 0, sheet, bool(a[1]), False), CellRef(r2, MAX_COLS - 1, sheet, bool(b[1]), False)
            )
        if not known:
            return BadRef()
        self.refs.append(area)
        return Area(area)
