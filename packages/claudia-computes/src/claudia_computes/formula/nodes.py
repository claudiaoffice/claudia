"""The syntax tree of a formula. Nodes are immutable; a rewrite builds a new tree and shares what did not change."""

from __future__ import annotations

from dataclasses import dataclass

from ..refs import CellRef, RangeRef


@dataclass(frozen=True, slots=True)
class Num:
    value: int | float
    text: str  # as typed (1.50 stays 1.50)


@dataclass(frozen=True, slots=True)
class Str:
    value: str


@dataclass(frozen=True, slots=True)
class Bool:
    value: bool


@dataclass(frozen=True, slots=True)
class ErrorLit:
    """An error typed into the formula (``#N/A``)."""

    code: str


@dataclass(frozen=True, slots=True)
class Ref:
    ref: CellRef


@dataclass(frozen=True, slots=True)
class Area:
    ref: RangeRef


@dataclass(frozen=True, slots=True)
class BadRef:
    """A reference that no longer points anywhere (``#REF!``)."""


@dataclass(frozen=True, slots=True)
class Name:
    text: str


@dataclass(frozen=True, slots=True)
class TableRef:
    """A structured reference, as Excel writes it: ``Sales[Amount]``, ``Sales[@[Unit price]]``, ``Sales[#Headers]``.

    ``items`` are the parts of the table asked for (``"#Headers"``, ``"#Data"``, ``"#All"``, ``"#This Row"``;
    none means the data rows), ``first`` and ``last`` the columns (``last`` only for a span ``[[A]:[B]]``; none at
    all means every column). Which cells that is depends on the table's definition in the workbook, so the tree
    only says what was typed (E6.5)."""

    table: str
    items: tuple[str, ...] = ()
    first: str | None = None
    last: str | None = None


@dataclass(frozen=True, slots=True)
class Missing:
    """An argument left out: ``IF(A1,,2)``."""


@dataclass(frozen=True, slots=True)
class Unary:
    op: str  # "-" or "+"
    operand: Node


@dataclass(frozen=True, slots=True)
class Percent:
    operand: Node


@dataclass(frozen=True, slots=True)
class Binary:
    op: str
    left: Node
    right: Node


@dataclass(frozen=True, slots=True)
class Paren:
    inner: Node


@dataclass(frozen=True, slots=True)
class Call:
    name: str  # upper case
    args: tuple[Node, ...]


Node = (
    Num
    | Str
    | Bool
    | ErrorLit
    | Ref
    | Area
    | BadRef
    | Name
    | TableRef
    | Missing
    | Unary
    | Percent
    | Binary
    | Paren
    | Call
)


def children(node: Node) -> tuple[Node, ...]:
    """The nodes directly inside ``node``."""
    match node:
        case Unary(operand=operand) | Percent(operand=operand):
            return (operand,)
        case Binary(left=left, right=right):
            return (left, right)
        case Paren(inner=inner):
            return (inner,)
        case Call(args=args):
            return args
    return ()


def walk(node: Node):
    """Every node of the tree, parents before children. Uses a list as its stack, so a long chain is no problem."""
    pending = [node]
    while pending:
        current = pending.pop()
        yield current
        pending.extend(reversed(children(current)))


#: Functions that ask only *where* a reference is, never what its cells hold. A reference passed straight to one of
#: them is no dependency: ``=COLUMNS($B$3:B3)`` in B3 counts columns and is not circular, as in Excel (D377).
SHAPE_ONLY = frozenset({"ROW", "COLUMN", "ROWS", "COLUMNS"})


def _unwrapped(node: Node) -> Node:
    while isinstance(node, Paren):
        node = node.inner
    return node


def _as_range(node: Ref | Area) -> RangeRef:
    return RangeRef(node.ref, node.ref) if isinstance(node, Ref) else node.ref


def shape_only_refs(node: Node) -> set[RangeRef]:
    """The references in the tree that are only ever passed straight to a function of :data:`SHAPE_ONLY`.

    A reference that also appears anywhere else (``ROWS(A1:A3)+SUM(A1:A3)``) is read, and is not in the set."""
    shape: set[RangeRef] = set()
    read: set[RangeRef] = set()
    pending = [node]
    while pending:
        current = pending.pop()
        if isinstance(current, Call) and current.name in SHAPE_ONLY:
            for arg in current.args:
                inner = _unwrapped(arg)
                if isinstance(inner, Ref | Area):
                    shape.add(_as_range(inner))
                else:
                    pending.append(arg)
            continue
        if isinstance(current, Ref | Area):
            read.add(_as_range(current))
        pending.extend(children(current))
    return shape - read
