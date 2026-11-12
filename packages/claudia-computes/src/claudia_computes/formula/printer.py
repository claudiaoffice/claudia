"""Formula text from a formula: what the person sees in the formula bar after a rewrite."""

from __future__ import annotations

from ..limits import MAX_COLS, MAX_ROWS
from ..refs import RangeRef, SheetId, SheetNames, column_name, quote_sheet_name
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
    TableRef,
    Unary,
)
from .syntax import Formula
from .tablespec import print_spec


def print_formula(formula: Formula, sheet_names: SheetNames | None = None) -> str:
    """The formula as text, with the current names of its sheets. A formula that could not be read prints as typed."""
    if formula.ast is None:
        return formula.source
    return "=" + print_node(formula.ast, sheet_names)


def print_node(node: Node, sheet_names: SheetNames | None = None) -> str:
    """One node as text. A chain such as ``1+2+3+...`` is walked in a loop: it is as deep as it is long."""
    tail: list[str] = []
    while isinstance(node, Binary):
        tail.append(node.op + _print(node.right, sheet_names))
        node = node.left
    return _print(node, sheet_names) + "".join(reversed(tail))


def _print(node: Node, names: SheetNames | None) -> str:
    try:
        printer = _PRINTERS[node.__class__]
    except KeyError:
        raise TypeError(node) from None
    return printer(node, names)


def _quoted(node: Str, names: SheetNames | None) -> str:
    return '"' + node.value.replace('"', '""') + '"'


_PRINTERS = {
    Num: lambda node, names: node.text,
    Str: _quoted,
    Bool: lambda node, names: "TRUE" if node.value else "FALSE",
    ErrorLit: lambda node, names: node.code,
    Ref: lambda node, names: node.ref.to_a1(names),
    Area: lambda node, names: _print_range(node.ref, names),
    BadRef: lambda node, names: "#REF!",
    Name: lambda node, names: node.text,
    TableRef: lambda node, names: node.table + print_spec(node.items, node.first, node.last),
    Missing: lambda node, names: "",
    Unary: lambda node, names: node.op + print_node(node.operand, names),
    Percent: lambda node, names: print_node(node.operand, names) + "%",
    Paren: lambda node, names: "(" + print_node(node.inner, names) + ")",
    Call: lambda node, names: node.name + "(" + ",".join([print_node(a, names) for a in node.args]) + ")",
    Binary: print_node,
}


def _print_range(ref: RangeRef, names: SheetNames | None) -> str:
    """``A1:B3``, or ``A:C`` / ``2:4`` for whole columns and rows."""
    first, last = ref.first, ref.last
    if first.row == 0 and last.row == MAX_ROWS - 1 and not first.row_abs and not last.row_abs:
        head = _sheet_prefix(first.sheet, names)
        if head is None:
            return "#REF!"
        a, b = ("$" if first.col_abs else ""), ("$" if last.col_abs else "")
        return f"{head}{a}{column_name(first.col)}:{b}{column_name(last.col)}"
    if first.col == 0 and last.col == MAX_COLS - 1 and not first.col_abs and not last.col_abs:
        head = _sheet_prefix(first.sheet, names)
        if head is None:
            return "#REF!"
        return f"{head}{'$' if first.row_abs else ''}{first.row + 1}:{'$' if last.row_abs else ''}{last.row + 1}"
    return ref.to_a1(names)


def _sheet_prefix(sheet: SheetId | None, names: SheetNames | None) -> str | None:
    if sheet is None:
        return ""
    name = names(sheet) if names else None
    return None if name is None else quote_sheet_name(name) + "!"
