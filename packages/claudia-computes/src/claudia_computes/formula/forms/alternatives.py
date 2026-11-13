"""Forms for alternatives: ALTERNATIVES and SCENARIOS (E6.21, D294).

``=ALTERNATIVES(800,1000,1300)`` is what a cell holds when its owner typed ``{800, 1000, 1300}``; the scenarios
``=SCENARIOS("low",800,"base",1000)`` have names. On its own a cell with alternatives shows its first one, so a sheet
that is opened in any other program still calculates. The calculator knows which cells are inputs of that kind
(``alternatives_of``) and runs the cells that depend on them once per alternative (``claudia_computes.outcomes``);
for that it asks the cell for its n-th alternative through ``Scope.choice``, which is why only the formula's top
call honours a choice."""

from __future__ import annotations

from ...refs import SheetNames
from ...values import VALUE
from ..compiler import Compiler, Evaluator, failing
from ..nodes import Bool, Call, Node, Num, Str, Unary
from ..printer import print_node
from . import form, wrong_count


def labels_of(node: Node | None) -> tuple[str | None, ...] | None:
    """The alternatives a formula's top call makes, as their names (``None`` for an unnamed one), or ``None`` when the
    formula is no well-formed ``ALTERNATIVES(...)`` or ``SCENARIOS(...)``."""
    if not isinstance(node, Call):
        return None
    if node.name == "ALTERNATIVES":
        return (None,) * len(node.args) if node.args else None
    if node.name == "SCENARIOS" and node.args and len(node.args) % 2 == 0:
        names = node.args[0::2]
        if all(isinstance(name, Str) for name in names):
            return tuple(name.value for name in names if isinstance(name, Str))
    return None


def items_of(node: Node | None) -> tuple[tuple[str | None, Node], ...] | None:
    """The alternatives a formula's top call makes, each as its name and the node that gives its value."""
    labels = labels_of(node)
    if labels is None or not isinstance(node, Call):
        return None
    values = node.args if node.name == "ALTERNATIVES" else node.args[1::2]
    return tuple(zip(labels, values, strict=True))


def brace_text(node: Node | None, sheet_names: SheetNames | None = None) -> str | None:
    """The alternatives as the person types them, ``{800, 1000, 1300}`` or ``{low: 800, base: =B2}``: a plain value
    is written as it is, anything else with the ``=`` of a formula. ``None`` when the formula is no list of
    alternatives."""
    items = items_of(node)
    if items is None:
        return None
    parts = []
    for label, value in items:
        text = print_node(value, sheet_names)
        plain = isinstance(value, (Num, Str, Bool)) or (isinstance(value, Unary) and isinstance(value.operand, Num))
        parts.append((f"{label}: " if label is not None else "") + (text if plain else "=" + text))
    return "{" + ", ".join(parts) + "}"


def _chooser(compiler: Compiler, args: tuple[Node, ...], values: list[Evaluator]) -> Evaluator:
    """An evaluator that gives the alternative the scope asks for (the first one unless this is the formula's top call
    and the calculator has chosen another)."""
    top = compiler.top_args is args

    def evaluate(scope):
        at = scope.choice.get((scope.home, scope.row, scope.col), 0) if top else 0
        return values[at if at < len(values) else 0](scope)

    return evaluate


@form("ALTERNATIVES")
def _alternatives(compiler: Compiler, args: tuple[Node, ...]) -> Evaluator:
    """ALTERNATIVES(value1, value2, ...): several values for one input. The cell shows the first; everything that
    depends on the cell is calculated for each of them (see Tools > Alternatives). Typed as {value1, value2, ...}."""
    if not args:
        return wrong_count("ALTERNATIVES", 0, 1, None)
    return _chooser(compiler, args, [compiler.compile(arg) for arg in args])


@form("SCENARIOS")
def _scenarios(compiler: Compiler, args: tuple[Node, ...]) -> Evaluator:
    """SCENARIOS("name1", value1, "name2", value2, ...): alternatives with names, typed as {name1: value1, ...}."""
    if labels_of(Call("SCENARIOS", args)) is None:
        return failing(
            VALUE, 'SCENARIOS takes pairs of a name in quotes and a value: SCENARIOS("low", 800, "base", 1000)'
        )
    return _chooser(compiler, args, [compiler.compile(arg) for arg in args[1::2]])
