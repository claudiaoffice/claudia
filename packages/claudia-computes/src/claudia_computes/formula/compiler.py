"""From a tree to something fast to run.

``Compiler.compile`` turns each node into a Python closure once, when the formula is entered; evaluating is then
just calling closures. A chain such as ``a+b+c+...`` becomes one loop, not a closure nested as deep as the chain is
long. Numbers and text are constants (and arithmetic on constants is done at once). The operators are in
``operators``; ``IF``, the lookup functions and the other functions that need to see their arguments unevaluated or as
references are *forms* (``forms``); every other function comes from the registry of user functions.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from ..functions.range import Range
from ..functions.registry import FunctionRegistry
from ..refs import SheetId
from ..values import NAME, REF, ErrorValue, FormulaError
from . import operators
from .nodes import Area, BadRef, Binary, Bool, Call, ErrorLit, Missing, Name, Node, Num, Paren, Percent, Ref, Str, Unary
from .scope import Scope

Evaluator = Callable[[Scope], Any]


class Absent:
    """The value of an argument that was left out (``IF(A1,,2)``)."""

    def __repr__(self) -> str:
        return "MISSING"


MISSING = Absent()


def constant(value: object) -> Evaluator:
    def evaluate(_: Scope) -> object:
        return value

    evaluate.constant = (value,)  # type: ignore[attr-defined]
    return evaluate


def constant_of(evaluator: Evaluator) -> tuple[object] | None:
    """``(value,)`` when the evaluator always gives the same value, else ``None``."""
    return getattr(evaluator, "constant", None)


def failing(code: str, detail: str = "") -> Evaluator:
    """An evaluator that always ends in an error (a name that does not exist, a reference that broke)."""

    def evaluate(_: Scope) -> object:
        raise FormulaError(code, detail)

    return evaluate


class Compiler:
    def __init__(self, registry: FunctionRegistry):
        self.registry = registry
        self._handlers: dict[type, Callable[[Any], Evaluator]] = {
            Num: self._literal,
            Str: self._literal,
            Bool: self._literal,
            ErrorLit: lambda node: failing(node.code),
            BadRef: lambda node: failing(REF, "a cell this formula used was deleted"),
            Name: lambda node: failing(NAME, f"there is nothing called {node.text!r}"),
            Missing: lambda node: constant(MISSING),
            Ref: lambda node: self.cell(node.ref.sheet, node.ref.row, node.ref.col),
            Area: self._area,
            Paren: lambda node: self.compile(node.inner),
            Unary: self._unary,
            Percent: lambda node: self.map(self.compile(node.operand), operators.percent),
            Binary: self.chain,
            Call: lambda node: self.call(node.name, node.args),
        }

    # -- the nodes
    def compile(self, node: Node) -> Evaluator:
        """An evaluator that gives the node's value: a number, text, TRUE/FALSE, empty (``None``) or a ``Range``.
        It raises ``FormulaError`` when the node ends in an error."""
        try:
            handler = self._handlers[node.__class__]
        except KeyError:
            raise TypeError(node) from None
        return handler(node)

    @staticmethod
    def _literal(node: Any) -> Evaluator:
        return constant(node.value)

    def _area(self, node: Area) -> Evaluator:
        ref = node.ref
        return self.area(ref.sheet, ref.first.row, ref.first.col, ref.last.row, ref.last.col)

    def _unary(self, node: Unary) -> Evaluator:
        inner = self.compile(node.operand)
        return inner if node.op == "+" else self.map(inner, operators.negate)

    def compile_range(self, node: Node) -> Evaluator:
        """An evaluator that gives a ``Range`` without reading the cells: for functions that need to know *where*
        (``ROW(A5)``, ``INDEX(A1:C3, 2, 2)``) and must not fail because the cell holds an error."""
        match node:
            case Ref(ref=ref):
                return self.area(ref.sheet, ref.row, ref.col, ref.row, ref.col)
            case Paren(inner=inside):
                return self.compile_range(inside)
        inner = self.compile(node)

        def evaluate(scope: Scope) -> Range:
            value = inner(scope)
            if value.__class__ is not Range:
                return Range.of_value(value)
            return value

        return evaluate

    # -- references
    @staticmethod
    def cell(sheet: SheetId | None, row: int, col: int) -> Evaluator:
        position = (row, col)
        if sheet is None:

            def home(scope: Scope) -> object:
                value = scope.grid.get(position)
                if value.__class__ is ErrorValue:
                    raise value.raised()
                return value

            return home

        def other(scope: Scope) -> object:
            value = scope.read(sheet, position)
            if value.__class__ is ErrorValue:
                raise value.raised()
            return value

        return other

    @staticmethod
    def area(sheet: SheetId | None, row0: int, col0: int, row1: int, col1: int) -> Evaluator:
        def evaluate(scope: Scope) -> Range:
            return scope.area(sheet, row0, col0, row1, col1)

        return evaluate

    # -- operators
    def map(self, inner: Evaluator, function: Callable[[Any], Any]) -> Evaluator:
        known = constant_of(inner)
        if known is not None:
            try:
                return constant(function(known[0]))
            except FormulaError:
                pass  # (it fails every time, but say so when the cell is evaluated, not when it is typed)

        def evaluate(scope: Scope) -> object:
            return function(inner(scope))

        return evaluate

    def chain(self, node: Binary) -> Evaluator:
        """``a op b op c ...`` as one evaluator: the operands in order, each combined with what came before."""
        spine: list[Binary] = []
        current: Node = node
        while isinstance(current, Binary):  # (a long chain leans to the left: walk it in a loop, not by recursion)
            spine.append(current)
            current = current.left
        first = self.compile(current)
        steps: list[tuple[Callable[[Any, Any], Any], Evaluator]] = [
            (operators.BINARY[binary.op], self.compile(binary.right)) for binary in reversed(spine)
        ]
        if len(steps) == 1:
            function, right = steps[0]
            return self.pair(first, function, right)

        def evaluate(scope: Scope) -> object:
            value = first(scope)
            for function, right in steps:
                value = function(value, right(scope))
            return value

        return evaluate

    @staticmethod
    def pair(left: Evaluator, function: Callable[[Any, Any], Any], right: Evaluator) -> Evaluator:
        known_left, known_right = constant_of(left), constant_of(right)
        if known_left is not None and known_right is not None:
            try:
                return constant(function(known_left[0], known_right[0]))
            except FormulaError:
                pass
        if known_right is not None:
            operand = known_right[0]

            def with_constant(scope: Scope) -> object:
                return function(left(scope), operand)

            return with_constant

        def evaluate(scope: Scope) -> object:
            return function(left(scope), right(scope))

        return evaluate

    # -- functions
    def call(self, name: str, args: tuple[Node, ...]) -> Evaluator:
        from .forms import FORMS  # (forms use the compiler, the compiler knows the table of forms)

        form = FORMS.get(name)
        if form is not None:
            return form(self, args)
        bound = self.registry.get(name)
        if bound is None:
            return failing(NAME, f"there is no function {name}")
        evaluators = [self.compile(arg) for arg in args]

        def evaluate(scope: Scope) -> object:
            return bound([None if (v := e(scope)) is MISSING else v for e in evaluators])

        return evaluate
