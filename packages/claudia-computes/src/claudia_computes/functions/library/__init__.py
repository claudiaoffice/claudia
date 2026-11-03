"""The functions that come with Claudia Computes: every one a ``UserFunction`` that takes values or ranges and gives
a value. Functions that choose what to evaluate or need to know where a reference points (``IF``, ``XLOOKUP``,
``INDEX`` ...) are in the core (``claudia_computes.formula.forms``), the arithmetic operators too."""

from __future__ import annotations

from ..base import UserFunction
from . import aggregate, criteria, logic, numeric, text  # noqa: F401  (importing the modules fills the catalog)
from .catalog import CLASSES


def builtin_classes() -> list[type[UserFunction]]:
    """Every built-in function class, in the order of the modules."""
    return list(CLASSES)
