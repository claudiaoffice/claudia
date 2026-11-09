"""Functions that can be used in formulas.

``help`` is not imported here on purpose: it reaches into ``formula.forms``, which reaches back into
``functions.range`` through ``formula.compiler`` while *this* module is still being loaded the first time (the
import that starts the chain is ``formula/compiler.py``'s own ``from ..functions.range import Range``) — importing
it eagerly here is a circular import. ``claudia_computes/__init__.py`` imports it later instead, once that chain has
already finished, and re-exports it from there."""

from .range import Range

__all__ = ["Range"]
