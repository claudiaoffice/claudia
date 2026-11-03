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


Node = Num | Str | Bool | ErrorLit | Ref | Area | BadRef | Name | Missing | Unary | Percent | Binary | Paren | Call


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
