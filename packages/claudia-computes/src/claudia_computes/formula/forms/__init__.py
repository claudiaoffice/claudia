"""The functions that belong to the core.

A *form* is a function that cannot be written as "values in, value out": it chooses which arguments to evaluate
(``IF``, ``IFERROR``), has to look at an error instead of failing on it (``ISERROR``), or needs to know *where* a
reference points rather than what it holds (``ROW``, ``INDEX``, ``XLOOKUP``, ``OFFSET``). Functions that merely
take values or ranges and give a value (``SUM``, ``MEDIAN``, ``LEFT`` ...) are not forms: they are ``UserFunction``s
(``claudia_computes.functions``), like the ones people write themselves.

A form is a function ``form(compiler, args) -> evaluator`` registered under its name with ``@form("NAME")``.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING

from ...values import VALUE, FormulaError, Value
from ..nodes import Node

if TYPE_CHECKING:
    from ..compiler import Compiler, Evaluator

Form = Callable[["Compiler", tuple[Node, ...]], "Evaluator"]
FORMS: dict[str, Form] = {}


def form(name: str) -> Callable[[Form], Form]:
    def register(function: Form) -> Form:
        FORMS[name] = function
        return function

    return register


def wrong_count(name: str, got: int, low: int, high: int | None) -> Evaluator:
    """An evaluator that says ``name`` was given the wrong number of arguments."""
    from ..compiler import failing

    wanted = str(low) if low == high else (f"at least {low}" if high is None else f"{low} to {high}")
    return failing(VALUE, f"{name} takes {wanted} arguments, not {got}")


def truth(value: Value | object) -> bool:
    """A value as TRUE or FALSE: a number is TRUE unless it is 0, empty is FALSE, the text "TRUE" or "FALSE" is that;
    other text and ranges are not conditions."""
    from ..operators import single

    value = single(value)
    if value.__class__ is bool:
        return value
    if value is None:
        return False
    if isinstance(value, (int, float)):
        return value != 0
    if isinstance(value, str) and value.strip().upper() in ("TRUE", "FALSE"):
        return value.strip().upper() == "TRUE"
    raise FormulaError(VALUE, "a condition must be TRUE or FALSE, or a number (0 is FALSE)")


from . import conditional, information, lookup, reference, sql  # noqa: E402, F401  (they register their forms)

CORE_NAMES = frozenset(FORMS)
