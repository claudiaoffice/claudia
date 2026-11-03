"""AND, OR, XOR, NOT, TRUE, FALSE. (IF and its relatives are in the core: they choose what to evaluate.)"""

from __future__ import annotations

from ...values import VALUE, ErrorValue
from ..base import Example, FunctionError, UserFunction
from ..range import Range
from .catalog import builtin


def truths(ranges: tuple[Range, ...]) -> list[bool]:
    """The logical values among the arguments: TRUE/FALSE, and numbers (0 is FALSE). Text and empty cells in a range
    are skipped; an error is raised; there must be at least one."""
    found: list[bool] = []
    for area in ranges:
        for value in area.present():
            if value.__class__ is bool:
                found.append(value)
            elif value.__class__ in (int, float):
                found.append(value != 0)
            elif value.__class__ is ErrorValue:
                raise value.raised()
    if not found:
        raise FunctionError(VALUE, "there is no logical value to look at")
    return found


@builtin
class AND(UserFunction):
    description = "TRUE if every value is TRUE (numbers: not 0); text and empty cells are skipped."
    examples = (Example("=AND(A1:A3)", False, {"A1": True, "A2": 1, "A3": 0}),)

    def call(self, *values: Range):
        return all(truths(values))


@builtin
class OR(UserFunction):
    description = "TRUE if any value is TRUE (numbers: not 0); text and empty cells are skipped."
    examples = (Example("=OR(A1:A3)", True, {"A1": False, "A2": 0, "A3": 5}),)

    def call(self, *values: Range):
        return any(truths(values))


@builtin
class XOR(UserFunction):
    description = "TRUE if an odd number of the values are TRUE."
    examples = (Example("=XOR(TRUE, TRUE, TRUE)", True),)

    def call(self, *values: Range):
        return sum(truths(values)) % 2 == 1


@builtin
class NOT(UserFunction):
    description = "TRUE becomes FALSE and FALSE becomes TRUE."
    examples = (Example("=NOT(FALSE)", True),)

    def call(self, value: bool):
        return not value


@builtin
class TRUE(UserFunction):
    description = "The logical value TRUE (it can also be written without brackets)."
    examples = (Example("=TRUE()", True),)

    def call(self):
        return True


@builtin
class FALSE(UserFunction):
    description = "The logical value FALSE (it can also be written without brackets)."
    examples = (Example("=FALSE()", False),)

    def call(self):
        return False
