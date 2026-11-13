"""What claudia has that other spreadsheets do not, in their files: random distributions and alternatives (E6.21-E6.22,
D292, D294, D299).

**Random numbers.** ``RAND()`` and ``RANDBETWEEN()`` are Excel's own and are written as they are.
``RANDOM("normal", 1000, 150)`` is not: it is written as the formula Excel would use, ``NORMINV(RAND(),1000,150)``,
and read back as ``RANDOM``, so a model survives the trip and a model that came from Excel with such formulas keeps
drawing from them. The older names (``NORMINV``, ``LOGINV``, ``BETAINV``, ``GAMMAINV``, ``CRITBINOM``) are used on
purpose: they are in the first file formats, need no ``_xlfn.`` prefix in an xlsx file, and are the names OpenFormula
has.

====================  ==========================================================================================
``uniform(a, b)``     ``a+(b-a)*RAND()``
``normal(m, s)``      ``NORMINV(RAND(),m,s)``
``lognormal(m, s)``   ``LOGINV(RAND(),m,s)``
``exponential(r)``    ``-LN(1-RAND())/r``
``weibull(k, l)``     ``l*(-LN(1-RAND()))^(1/k)``
``beta(a, b)``        ``BETAINV(RAND(),a,b)``
``gamma(k, t)``       ``GAMMAINV(RAND(),k,t)``
``pert(a, m, b)``     ``a+(b-a)*BETAINV(RAND(),1+4*(m-a)/(b-a),1+4*(b-m)/(b-a))``
``binomial(n, p)``    ``CRITBINOM(n,p,RAND())``
``discrete(...)``     ``LOOKUP(RAND(),{0,c1,...},{v1,v2,...})`` when the values and weights are written out
====================  ==========================================================================================

A cut distribution (``low`` and ``high``) squeezes the draw into the part of the distribution between them with its
cumulative function. Triangular and Poisson draws, and a discrete one whose numbers are in cells, have no formula that
draws once, so they are written as their value (a loss, ``formula:random``): Excel would otherwise draw a new number
for each time the formula names its draw.

**Alternatives.** ``{800, 1000, 1300}`` is written as its first alternative, which every program can show, with a note
on the cell that says what the others are; claudia reads the note back (when the cell still holds the first
alternative) and other programs show it as an ordinary comment.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass

from claudia_computes import Content, parse_input
from claudia_computes.alternatives import formula_for, parse_alternatives
from claudia_computes.distributions import DISTRIBUTIONS
from claudia_computes.formula import (
    Binary,
    Bool,
    Call,
    Missing,
    Name,
    Node,
    Num,
    Paren,
    Percent,
    Str,
    Unary,
    parse_formula,
    print_formula,
    print_node,
)
from claudia_computes.formula.forms.alternatives import brace_text, items_of
from claudia_computes.refs import SheetId

from .openformula import Untranslatable

SheetIds = Callable[[str], SheetId | None]  # a sheet's name -> its id, for reading formulas that name sheets


def _as_written(name: str) -> SheetId:
    """A sheet is its own name here: a formula's text is changed, what it says about sheets stays as written."""
    return SheetId(name)


def _name_as_written(sheet: SheetId) -> str:
    return str(sheet)


NOTE_MARKER = "claudia alternatives: "
RANDOM_REASON = "random"  # what a loss of a draw that Excel cannot say is called

_ATOMS = (Num, Str, Bool, Call, Paren)


# ------------------------------------------------------------------------------------------------ the tree
def _map_nodes(node: Node, change: Callable[[Node], Node]) -> Node:
    """``change`` applied to every node, the ones inside first; ``node`` itself comes back when nothing changed."""
    if isinstance(node, Binary):
        spine: list[Binary] = []
        while isinstance(node, Binary):  # a chain 1+2+3+... leans left: walk down it in a loop
            spine.append(node)
            node = node.left
        built = _map_nodes(node, change)
        for outer in reversed(spine):
            right = _map_nodes(outer.right, change)
            rebuilt = outer if built is outer.left and right is outer.right else Binary(outer.op, built, right)
            built = change(rebuilt)
        return built
    if isinstance(node, Unary):
        inner = _map_nodes(node.operand, change)
        return change(node if inner is node.operand else Unary(node.op, inner))
    if isinstance(node, Percent):
        inner = _map_nodes(node.operand, change)
        return change(node if inner is node.operand else Percent(inner))
    if isinstance(node, Paren):
        inner = _map_nodes(node.inner, change)
        return change(node if inner is node.inner else Paren(inner))
    if isinstance(node, Call):
        args = tuple(_map_nodes(a, change) for a in node.args)
        same = all(new is old for new, old in zip(args, node.args, strict=True))
        return change(node if same else Call(node.name, args))
    return change(node)


def _rewrite(text: str, change: Callable[[Node], Node]) -> str:
    """The formula ``text`` with ``change`` applied to every node of it (unchanged text comes back as it is)."""
    formula = parse_formula(text, _as_written)
    if formula.ast is None:
        return text
    changed = _map_nodes(formula.ast, change)
    return text if changed is formula.ast else "=" + print_node(changed, _name_as_written)


# ------------------------------------------------------------------------------------------------ RANDOM to Excel
@dataclass(frozen=True, slots=True)
class _Parameters:
    """The arguments of a ``RANDOM`` call as text for a larger formula, and which of them are plain numbers."""

    text: list[str]
    numbers: list[float | None]
    low: str | None
    high: str | None


def _atom(node: Node) -> str:
    text = print_node(node, _name_as_written)
    return text if isinstance(node, _ATOMS) else f"({text})"


def _number_of(node: Node) -> float | None:
    if isinstance(node, Num):
        return node.value
    if isinstance(node, Unary) and isinstance(node.operand, Num):
        return -node.operand.value if node.op == "-" else node.operand.value
    return None


def _parameters(distribution_arity: int | None, args: tuple[Node, ...]) -> _Parameters:
    count = len(args) if distribution_arity is None else distribution_arity
    body, limits = args[:count], args[count:]
    low = high = None
    if limits:
        low = None if isinstance(limits[0], Missing) else _atom(limits[0])
        high = None if len(limits) < 2 or isinstance(limits[1], Missing) else _atom(limits[1])
    return _Parameters([_atom(a) for a in body], [_number_of(a) for a in body], low, high)


def _inverse(name: str, p: _Parameters, u: str) -> str:
    t = p.text
    match name:
        case "uniform":
            return f"{t[0]}+({t[1]}-{t[0]})*{u}"
        case "normal":
            return f"NORMINV({u},{t[0]},{t[1]})"
        case "lognormal":
            return f"LOGINV({u},{t[0]},{t[1]})"
        case "exponential":
            return f"-LN(1-{u})/{t[0]}"
        case "weibull":
            return f"{t[1]}*(-LN(1-{u}))^(1/{t[0]})"
        case "beta":
            return f"BETAINV({u},{t[0]},{t[1]})"
        case "gamma":
            return f"GAMMAINV({u},{t[0]},{t[1]})"
        case "pert":
            low, mode, high = t
            spread = f"({high}-{low})"
            shapes = f"1+4*({mode}-{low})/{spread},1+4*({high}-{mode})/{spread}"
            return f"{low}+{spread}*BETAINV({u},{shapes})"
        case "binomial":
            return f"CRITBINOM({t[0]},{t[1]},{u})"
    raise Untranslatable(RANDOM_REASON, name)


def _cumulative(name: str, p: _Parameters, x: str) -> str:
    """The cumulative distribution at the written-out ``x`` (put where the distribution has no values: at its edge)."""
    t = p.text
    positive = f"MAX(0,{x})"
    match name:
        case "uniform":
            return f"MEDIAN(0,({x}-{t[0]})/({t[1]}-{t[0]}),1)"
        case "normal":
            return f"NORMDIST({x},{t[0]},{t[1]},TRUE)"
        case "lognormal":
            return f"LOGNORMDIST(MAX({x},1E-300),{t[0]},{t[1]})"
        case "exponential":
            return f"(1-EXP(-{t[0]}*{positive}))"
        case "weibull":
            return f"WEIBULL({positive},{t[0]},{t[1]},TRUE)"
        case "beta":
            return f"BETADIST(MEDIAN(0,{x},1),{t[0]},{t[1]})"
        case "gamma":
            return f"GAMMADIST({positive},{t[0]},{t[1]},TRUE)"
        case "pert":
            low, mode, high = t
            spread = f"({high}-{low})"
            shapes = f"1+4*({mode}-{low})/{spread},1+4*({high}-{mode})/{spread}"
            return f"BETADIST(MEDIAN(0,({x}-{low})/{spread},1),{shapes})"
    raise Untranslatable(RANDOM_REASON, f"{name} cannot be cut")


def _discrete(p: _Parameters) -> str:
    numbers = p.numbers
    if any(n is None for n in numbers) or len(numbers) % 2:
        raise Untranslatable(RANDOM_REASON, "discrete: the values and weights must be written out")
    values, weights = numbers[0::2], numbers[1::2]
    total = sum(weights)  # type: ignore[arg-type]
    running, edges = 0.0, []
    for weight in weights[:-1]:
        running += weight  # type: ignore[operator]
        edges.append(repr(running / total))
    shown = ",".join(f"{v:g}" if isinstance(v, float) else str(v) for v in values)
    return f"LOOKUP(RAND(),{{0,{','.join(edges)}}},{{{shown}}})" if edges else f"{values[0]:g}"


def _is_one_call(text: str) -> bool:
    """Whether ``text`` is a single function call (``NORMINV(...)``), which needs no brackets around it."""
    if not re.fullmatch(r"[A-Z][A-Z.]*\(.*\)", text):
        return False
    depth = 0
    for at, char in enumerate(text):
        depth += char == "("
        depth -= char == ")"
        if char == ")" and depth == 0 and at < len(text) - 1:  # (the bracket that opened the call closed early)
            return False
    return True


def _excel_random(call: Call) -> str:
    """The Excel text that draws what ``RANDOM(...)`` draws."""
    if not call.args:
        return "RAND()"
    name_node = call.args[0]
    if not isinstance(name_node, Str):
        raise Untranslatable(RANDOM_REASON, "the distribution must be written out")
    distribution = DISTRIBUTIONS.get(name_node.value.casefold())
    if distribution is None:
        raise Untranslatable("function", f"RANDOM({name_node.value})")
    p = _parameters(distribution.arity, call.args[1:])
    if distribution.name in ("triangular", "poisson"):
        raise Untranslatable(RANDOM_REASON, distribution.name)
    if distribution.name == "discrete":
        return _discrete(p)
    if p.low is None and p.high is None:
        return _inverse(distribution.name, p, "RAND()")
    low = "0" if p.low is None else _cumulative(distribution.name, p, p.low)
    high = "1" if p.high is None else _cumulative(distribution.name, p, p.high)
    return _inverse(distribution.name, p, f"({low}+RAND()*({high}-{low}))")


def to_excel(text: str) -> str:
    """The formula ``text`` of the model as Excel and OpenFormula know it: every ``RANDOM(...)`` becomes the formula
    that draws the same distribution. ``Untranslatable`` (reason ``random``) for one that cannot be said."""

    def change(node: Node) -> Node:
        if not (isinstance(node, Call) and node.name == "RANDOM"):
            return node
        written = _excel_random(node)
        return Name(written if _is_one_call(written) else f"({written})")  # (printed as it is: Excel's own text)

    if "RANDOM" not in text.upper():
        return text
    written = _rewrite(text, change)
    whole = parse_formula(text, _as_written).ast
    if (
        isinstance(whole, Call)
        and whole.name == "RANDOM"
        and written.startswith("=(")
        and not _is_one_call(written[1:])
    ):
        return "=" + written[2:-1]  # (the call was the whole formula: no brackets needed)
    return written


# ------------------------------------------------------------------------------------------------ Excel to RANDOM
_INVERSES = {  # Excel name -> (distribution, position of the uniform draw among the arguments, parameters it takes)
    "NORMINV": ("normal", 0, 2),
    "NORM.INV": ("normal", 0, 2),
    "LOGINV": ("lognormal", 0, 2),
    "LOGNORM.INV": ("lognormal", 0, 2),
    "BETAINV": ("beta", 0, 2),
    "BETA.INV": ("beta", 0, 2),
    "GAMMAINV": ("gamma", 0, 2),
    "GAMMA.INV": ("gamma", 0, 2),
    "CRITBINOM": ("binomial", 2, 2),
    "BINOM.INV": ("binomial", 2, 2),
}
_STANDARD_NORMAL = ("NORMSINV", "NORM.S.INV")
INVERSE_NAMES = frozenset(_INVERSES) | frozenset(_STANDARD_NORMAL)  # the functions :func:`from_excel` reads as RANDOM
_FUTURE = ("_XLFN.", "_XLWS.")


def _is_draw(node: Node) -> bool:
    return isinstance(node, Call) and node.name == "RAND" and not node.args


def _plain_name(name: str) -> str:
    for prefix in _FUTURE:
        if name.startswith(prefix):
            return name[len(prefix) :]
    return name


def from_excel(text: str) -> str:
    """The formula ``text`` of an Excel or OpenFormula file as the model writes it: ``NORMINV(RAND(),m,s)`` and the
    other inverse functions of a draw become ``RANDOM("normal", m, s)``; everything else stays."""

    def change(node: Node) -> Node:
        if not isinstance(node, Call):
            return node
        name = _plain_name(node.name)
        if name in _STANDARD_NORMAL and len(node.args) == 1 and _is_draw(node.args[0]):
            return Call("RANDOM", (Str("normal"), Num(0, "0"), Num(1, "1")))
        known = _INVERSES.get(name)
        if known is None:
            return node
        distribution, at, count = known
        if len(node.args) == 3 and _is_draw(node.args[at]):
            parameters = tuple(a for i, a in enumerate(node.args) if i != at)
            assert len(parameters) == count
            return Call("RANDOM", (Str(distribution), *parameters))
        return node

    upper = text.upper()
    if "RAND()" not in upper.replace(" ", "") and "NORMSINV" not in upper and "NORM.S.INV" not in upper:
        return text
    return _rewrite(text, change)


# ------------------------------------------------------------------------------------------------ alternatives
@dataclass(frozen=True, slots=True)
class Written:
    """A cell as another program's file holds it: the content (its first alternative, when it has alternatives) and the
    note that says what all the alternatives are (``None`` when there are none)."""

    content: Content
    note: str | None = None


def _first_content(node: Node) -> Content:
    match node:
        case Num(value=value):
            return {"t": "int" if isinstance(value, int) else "float", "v": value}
        case Str(value=value):
            return {"t": "text", "v": value}
        case Bool(value=value):
            return {"t": "bool", "v": value}
    number = _number_of(node)
    if number is not None:
        return {"t": "int" if isinstance(number, int) else "float", "v": number}
    return {"t": "formula", "v": "=" + print_node(node, _name_as_written)}


def with_note(content: Content) -> Written:
    """What to write for ``content``: a cell with alternatives gives its first one and a note, anything else itself."""
    if content is None or content["t"] != "formula":
        return Written(content)
    formula = parse_formula(content["v"], _as_written)
    items = items_of(formula.ast)
    if items is None or len(items) < 2:
        return Written(content)
    note = NOTE_MARKER + (brace_text(formula.ast, _name_as_written) or "")
    return Written(_first_content(items[0][1]), note)


def _same(a: Content, b: Content) -> bool:
    if a is None or b is None:
        return a is b
    if a["t"] == "formula" and b["t"] == "formula":
        return _canonical(a["v"]) == _canonical(b["v"])
    return a == b or (a["t"] in ("int", "float") and b["t"] in ("int", "float") and a["v"] == b["v"])


def _canonical(text: str) -> str:
    return print_formula(parse_formula(text, _as_written), _name_as_written)


def restore_alternatives(content: Content, note: str | None) -> Content:
    """The cell as the model has it: a note written by :func:`with_note` on a cell that still holds the first
    alternative gives the alternatives back; anything else is the content as it is."""
    if note is None or not note.startswith(NOTE_MARKER):
        return content
    alternatives = parse_alternatives(note[len(NOTE_MARKER) :].strip())
    if alternatives is None or len(alternatives) < 2:
        return content
    restored = parse_input(formula_for(alternatives))
    written = with_note(restored)
    return restored if _same(content, written.content) else content


__all__ = [
    "INVERSE_NAMES",
    "NOTE_MARKER",
    "RANDOM_REASON",
    "Written",
    "from_excel",
    "restore_alternatives",
    "to_excel",
    "with_note",
]
