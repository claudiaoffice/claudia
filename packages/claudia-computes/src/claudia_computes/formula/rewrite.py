"""Formulas that follow their cells.

Everything that changes what a reference points at goes through here: a row or column inserted or deleted, a formula
copied somewhere else, a sheet removed. Each function returns the formula it was given, the same object, when nothing
changed, so the caller can tell by identity and a sheet of thousands of formulas costs only a look at each.
Nodes are rebuilt only along the path to a changed reference.
"""

from __future__ import annotations

from collections.abc import Callable

from ..limits import MAX_COLS, MAX_ROWS
from ..refs import CellRef, RangeRef, SheetId, SheetNames, StructuralEdit
from .nodes import Area, BadRef, Binary, Call, Name, Node, Paren, Percent, Ref, TableRef, Unary, walk
from .printer import print_formula
from .syntax import Formula

OnRef = Callable[[CellRef], CellRef | None]
OnRange = Callable[[RangeRef], RangeRef | None]


Leaf = Callable[[Node], Node]


def map_leaves(node: Node, leaf: Leaf) -> Node:
    """The tree with ``leaf`` applied to every node that has no nodes inside it; the nodes above are rebuilt only
    where something below changed, so unchanged parts are shared (and ``node`` itself comes back when nothing did)."""
    if isinstance(node, Binary):
        spine: list[Binary] = []
        while isinstance(node, Binary):  # a chain 1+2+3+... leans left: walk down it in a loop
            spine.append(node)
            node = node.left
        built = map_leaves(node, leaf)
        for outer in reversed(spine):
            right = map_leaves(outer.right, leaf)
            built = outer if built is outer.left and right is outer.right else Binary(outer.op, built, right)
        return built
    match node:
        case Unary(op=op, operand=operand):
            inner = map_leaves(operand, leaf)
            return node if inner is operand else Unary(op, inner)
        case Percent(operand=operand):
            inner = map_leaves(operand, leaf)
            return node if inner is operand else Percent(inner)
        case Paren(inner=inner):
            changed = map_leaves(inner, leaf)
            return node if changed is inner else Paren(changed)
        case Call(name=name, args=args):
            mapped = tuple(map_leaves(a, leaf) for a in args)
            return node if all(new is old for new, old in zip(mapped, args, strict=True)) else Call(name, mapped)
    return leaf(node)


def transform(node: Node, on_ref: OnRef, on_range: OnRange) -> Node:
    """The tree with every reference mapped; a reference mapped to ``None`` becomes a broken one.
    Returns ``node`` itself when no reference changed."""

    def leaf(here: Node) -> Node:
        match here:
            case Ref(ref=ref):
                new = on_ref(ref)
                if new is None:
                    return BadRef()
                return here if new == ref else Ref(new)
            case Area(ref=ref):
                new_range = on_range(ref)
                if new_range is None:
                    return BadRef()
                return here if new_range == ref else Area(new_range)
        return here

    return map_leaves(node, leaf)


def _rebuilt(formula: Formula, ast: Node, names: SheetNames | None) -> Formula:
    """``formula`` with a new tree: its text is printed again and its references collected again."""
    refs: list[RangeRef] = []
    for node in walk(ast):
        if isinstance(node, Ref):
            refs.append(RangeRef(node.ref, node.ref))
        elif isinstance(node, Area):
            refs.append(node.ref)
    draft = Formula(formula.source, ast, formula.error, tuple(dict.fromkeys(refs)), formula.dynamic)
    return Formula(print_formula(draft, names), ast, formula.error, draft.refs, formula.dynamic)


def _full_height(area: RangeRef) -> bool:
    return area.first.row == 0 and area.last.row == MAX_ROWS - 1


def _full_width(area: RangeRef) -> bool:
    return area.first.col == 0 and area.last.col == MAX_COLS - 1


# ------------------------------------------------------------------------------------ structural edits
def adjusted(formula: Formula, edit: StructuralEdit, home: SheetId, names: SheetNames | None = None) -> Formula:
    """The formula after rows or columns were inserted or deleted. ``home`` is the sheet the formula is on."""
    if formula.ast is None:
        return formula

    def on_ref(ref: CellRef) -> CellRef | None:
        new = ref.adjusted(edit, home)
        if new is not None and (new.row >= MAX_ROWS or new.col >= MAX_COLS):
            return None  # (pushed off the sheet)
        return new

    def on_range(area: RangeRef) -> RangeRef | None:
        new = area.adjusted(edit, home)
        if new is None or new.first.row >= MAX_ROWS or new.first.col >= MAX_COLS:
            return None
        first = new.first
        last = new.last
        if last.row >= MAX_ROWS or last.col >= MAX_COLS:
            last = CellRef(
                min(last.row, MAX_ROWS - 1), min(last.col, MAX_COLS - 1), last.sheet, last.row_abs, last.col_abs
            )
        if _full_height(area):  # (a whole column stays whole, whatever is inserted above or below it)
            first, last = first.with_row(0), last.with_row(MAX_ROWS - 1)
        if _full_width(area):
            first, last = first.with_col(0), last.with_col(MAX_COLS - 1)
        return RangeRef(first, last)

    ast = transform(formula.ast, on_ref, on_range)
    return formula if ast is formula.ast else _rebuilt(formula, ast, names)


def shifted(formula: Formula, d_row: int, d_col: int, names: SheetNames | None = None) -> Formula:
    """The formula as copied ``d_row`` rows and ``d_col`` columns away: relative references move with it, ``$`` parts
    stay, and a reference pushed off the sheet breaks."""
    if formula.ast is None or (d_row == 0 and d_col == 0):
        return formula

    def on_ref(ref: CellRef) -> CellRef | None:
        moved = ref.offset(d_row, d_col)
        return moved if moved is not None and moved.row < MAX_ROWS and moved.col < MAX_COLS else None

    def on_range(area: RangeRef) -> RangeRef | None:
        rows = 0 if _full_height(area) else d_row  # (a whole column does not slide down, a whole row not sideways)
        cols = 0 if _full_width(area) else d_col
        first, last = area.first.offset(rows, cols), area.last.offset(rows, cols)
        if first is None or last is None or last.row >= MAX_ROWS or last.col >= MAX_COLS:
            return None
        return RangeRef(first, last)

    ast = transform(formula.ast, on_ref, on_range)
    return formula if ast is formula.ast else _rebuilt(formula, ast, names)


def without_sheet(formula: Formula, sheet: SheetId, names: SheetNames | None = None) -> Formula:
    """The formula after ``sheet`` was removed: every reference to it breaks."""
    if formula.ast is None or not any(area.sheet == sheet for area in formula.refs):
        return formula
    ast = transform(
        formula.ast,
        lambda ref: None if ref.sheet == sheet else ref,
        lambda area: None if area.sheet == sheet else area,
    )
    return formula if ast is formula.ast else _rebuilt(formula, ast, names)


# ------------------------------------------------------------------------------------ names and columns
def renamed_name(formula: Formula, old: str, new: str, names: SheetNames | None = None) -> Formula:
    """The formula after the name or table ``old`` (compared without regard to case) was called ``new``."""
    if formula.ast is None:
        return formula
    wanted = old.casefold()

    def leaf(node: Node) -> Node:
        if isinstance(node, Name) and node.text.casefold() == wanted:
            return Name(new)
        if isinstance(node, TableRef) and node.table.casefold() == wanted:
            return TableRef(new, node.items, node.first, node.last)
        return node

    ast = map_leaves(formula.ast, leaf)
    return formula if ast is formula.ast else _rebuilt(formula, ast, names)


def renamed_column(formula: Formula, table: str, old: str, new: str, names: SheetNames | None = None) -> Formula:
    """The formula after the column ``old`` of ``table`` was called ``new`` (both without regard to case)."""
    if formula.ast is None:
        return formula
    wanted_table, wanted = table.casefold(), old.casefold()

    def rename(column: str | None) -> str | None:
        return new if column is not None and column.casefold() == wanted else column

    def leaf(node: Node) -> Node:
        if isinstance(node, TableRef) and node.table.casefold() == wanted_table:
            first, last = rename(node.first), rename(node.last)
            if (first, last) != (node.first, node.last):
                return TableRef(node.table, node.items, first, last)
        return node

    ast = map_leaves(formula.ast, leaf)
    return formula if ast is formula.ast else _rebuilt(formula, ast, names)
